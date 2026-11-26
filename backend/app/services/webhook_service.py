import hashlib
import json
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.payments import (
    PaymentAttempt,
    PaymentOrder,
    PaymentProviderAccount,
    PaymentTransaction,
    PaymentWebhookEvent,
)
from app.models.retail import Order, OrderEvent
from app.models.rossmann import AuditLog
from app.services.payment_service import (
    _decrypt_credentials,
    apply_verified_payment_capture,
    default_adapter_factory,
)


def _extract_entities(payload: dict) -> tuple[str | None, dict | None, dict | None]:
    inner = payload.get("payload") or {}
    payment_entity = (inner.get("payment") or {}).get("entity")
    order_entity = (inner.get("order") or {}).get("entity")

    provider_order_id = None
    if isinstance(payment_entity, dict) and payment_entity.get("order_id"):
        provider_order_id = str(payment_entity["order_id"])
    elif isinstance(order_entity, dict) and order_entity.get("id"):
        provider_order_id = str(order_entity["id"])

    return provider_order_id, payment_entity, order_entity


def _derive_event_id(
    payload: dict,
    header_event_id: str | None,
    event_type: str,
    provider_order_id: str | None,
    payment_entity: dict | None,
    payload_hash: str,
) -> str:
    if header_event_id and header_event_id.strip():
        return header_event_id.strip()[:120]
    if payload.get("event_id"):
        return str(payload["event_id"])[:120]
    payment_id = (
        str(payment_entity["id"])
        if isinstance(payment_entity, dict) and payment_entity.get("id")
        else ""
    )
    created_at = payload.get("created_at") or ""
    composite = f"{event_type}:{provider_order_id or ''}:{payment_id}:{created_at}:{payload_hash[:12]}"
    return hashlib.sha256(composite.encode("utf-8")).hexdigest()[:64]


def _build_sanitized_summary(
    event_type: str,
    provider_order_id: str | None,
    payment_entity: dict | None,
) -> dict:
    summary: dict = {
        "event": event_type,
        "provider_order_id": provider_order_id,
    }
    if isinstance(payment_entity, dict):
        summary["provider_payment_id"] = payment_entity.get("id")
        summary["status"] = payment_entity.get("status")
        summary["amount_minor"] = payment_entity.get("amount")
        summary["currency"] = payment_entity.get("currency")
        summary["method"] = payment_entity.get("method")
        if payment_entity.get("error_code"):
            summary["error_code"] = payment_entity.get("error_code")
    return summary


def _upsert_non_capture_attempt_and_txn(
    db: Session,
    *,
    organisation_id: int,
    order: Order,
    po: PaymentOrder,
    provider_payment_id: str,
    target_status: str,
    amount_minor: int,
    currency: str,
    method: str | None,
    failure_code: str | None = None,
    failure_reason: str | None = None,
    metadata: dict | None = None,
) -> None:
    now = datetime.now(timezone.utc)
    attempt = db.scalar(
        select(PaymentAttempt)
        .where(
            PaymentAttempt.provider == po.provider,
            PaymentAttempt.provider_payment_id == provider_payment_id,
        )
        .with_for_update()
    )
    if attempt is None:
        attempt = PaymentAttempt(
            organisation_id=organisation_id,
            payment_order_id=po.id,
            order_id=order.id,
            provider=po.provider,
            provider_payment_id=provider_payment_id,
            status=target_status,
            failure_code=failure_code,
            failure_reason=failure_reason,
            signature_verified=True,
        )
        db.add(attempt)
        db.flush()
    elif attempt.status != "CAPTURED":
        attempt.status = target_status
        attempt.failure_code = failure_code
        attempt.failure_reason = failure_reason
        attempt.signature_verified = True
        attempt.updated_at = now

    existing_txn = db.scalar(
        select(PaymentTransaction).where(
            PaymentTransaction.provider == po.provider,
            PaymentTransaction.provider_payment_id == provider_payment_id,
            PaymentTransaction.event_type == target_status,
        )
    )
    if existing_txn is None:
        db.add(
            PaymentTransaction(
                organisation_id=organisation_id,
                order_id=order.id,
                payment_order_id=po.id,
                payment_attempt_id=attempt.id,
                provider=po.provider,
                provider_payment_id=provider_payment_id,
                event_type=target_status,
                amount_minor=amount_minor,
                currency=currency.upper(),
                status=target_status,
                method=method,
                source="webhook",
                metadata_json=metadata,
            )
        )


def process_razorpay_webhook(
    db: Session,
    *,
    raw_body: bytes,
    signature: str | None,
    header_event_id: str | None = None,
) -> dict:
    if not signature or not signature.strip():
        raise HTTPException(
            status_code=400, detail="Missing X-Razorpay-Signature header."
        )

    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid JSON webhook payload.") from exc

    if not isinstance(payload, dict) or not payload.get("event"):
        raise HTTPException(status_code=400, detail="Malformed webhook payload.")

    event_type = str(payload["event"]).strip()
    payload_hash = hashlib.sha256(raw_body).hexdigest()
    provider_order_id, payment_entity, _ = _extract_entities(payload)
    provider_payment_id = (
        str(payment_entity["id"])
        if isinstance(payment_entity, dict) and payment_entity.get("id")
        else None
    )
    provider_event_id = _derive_event_id(
        payload,
        header_event_id,
        event_type,
        provider_order_id,
        payment_entity,
        payload_hash,
    )

    if not provider_order_id:
        raise HTTPException(
            status_code=400, detail="Webhook payload missing gateway order reference."
        )

    po = db.scalar(
        select(PaymentOrder)
        .where(
            PaymentOrder.provider == "razorpay",
            PaymentOrder.provider_order_id == provider_order_id,
        )
        .with_for_update()
    )
    if po is None:
        raise HTTPException(
            status_code=404, detail="Unknown payment order for webhook."
        )

    account = db.get(PaymentProviderAccount, po.provider_account_id)
    if account is None:
        raise HTTPException(
            status_code=404, detail="Gateway account for payment order not found."
        )

    creds = _decrypt_credentials(account)
    adapter = default_adapter_factory("razorpay")
    sanitized = _build_sanitized_summary(event_type, provider_order_id, payment_entity)

    if not adapter.verify_webhook(raw_body, signature, creds.webhook_secret):
        now = datetime.now(timezone.utc)
        existing_rej = db.scalar(
            select(PaymentWebhookEvent).where(
                PaymentWebhookEvent.provider == "razorpay",
                PaymentWebhookEvent.provider_event_id == provider_event_id,
            )
        )
        if existing_rej is None:
            db.add(
                PaymentWebhookEvent(
                    organisation_id=po.organisation_id,
                    provider_account_id=account.id,
                    provider="razorpay",
                    provider_event_id=provider_event_id,
                    event_type=event_type,
                    provider_order_id=provider_order_id,
                    provider_payment_id=provider_payment_id,
                    signature_valid=False,
                    processing_status="rejected_signature",
                    payload_hash=payload_hash,
                    sanitized_summary=sanitized,
                    error_message="Invalid X-Razorpay-Signature",
                    processed_at=now,
                )
            )
            db.commit()
        raise HTTPException(status_code=401, detail="Invalid webhook signature.")

    existing_event = db.scalar(
        select(PaymentWebhookEvent)
        .where(
            PaymentWebhookEvent.provider == "razorpay",
            PaymentWebhookEvent.provider_event_id == provider_event_id,
        )
        .with_for_update()
    )
    if existing_event is not None and existing_event.processing_status in (
        "processed",
        "ignored_duplicate",
        "ignored_out_of_order",
    ):
        return {
            "status": "ignored_duplicate",
            "event_type": event_type,
            "provider_event_id": provider_event_id,
        }

    order = db.scalar(
        select(Order).where(Order.id == po.order_id).with_for_update()
    )
    if order is None:
        raise HTTPException(status_code=404, detail="Linked order not found.")

    now = datetime.now(timezone.utc)
    if existing_event is None:
        event_row = PaymentWebhookEvent(
            organisation_id=po.organisation_id,
            provider_account_id=account.id,
            provider="razorpay",
            provider_event_id=provider_event_id,
            event_type=event_type,
            provider_order_id=provider_order_id,
            provider_payment_id=provider_payment_id,
            signature_valid=True,
            processing_status="received",
            payload_hash=payload_hash,
            sanitized_summary=sanitized,
        )
        db.add(event_row)
        try:
            db.flush()
        except IntegrityError:
            db.rollback()
            return {
                "status": "ignored_duplicate",
                "event_type": event_type,
                "provider_event_id": provider_event_id,
            }
    else:
        event_row = existing_event
        event_row.signature_valid = True
        event_row.payload_hash = payload_hash
        event_row.sanitized_summary = sanitized

    processing_status = "processed"

    if event_type in ("payment.captured", "order.paid"):
        if not isinstance(payment_entity, dict) or not provider_payment_id:
            if po.status == "CAPTURED" and order.order_status == "PAID":
                processing_status = "ignored_duplicate"
            else:
                processing_status = "ignored_out_of_order"
        else:
            amount_minor = int(payment_entity.get("amount") or po.amount_minor)
            currency = str(payment_entity.get("currency") or po.currency).upper()
            method = payment_entity.get("method")
            if po.status == "CAPTURED" and order.order_status == "PAID":
                processing_status = "ignored_duplicate"
            else:
                newly_captured = apply_verified_payment_capture(
                    db,
                    organisation_id=po.organisation_id,
                    order=order,
                    po=po,
                    provider_payment_id=provider_payment_id,
                    amount_minor=amount_minor,
                    currency=currency,
                    method=method,
                    source="webhook",
                    actor_ref="webhook:razorpay",
                    metadata={
                        "provider_event_id": provider_event_id,
                        "event_type": event_type,
                    },
                )
                processing_status = (
                    "processed" if newly_captured else "ignored_duplicate"
                )
    elif event_type == "payment.authorized":
        if po.status == "CAPTURED" or order.order_status == "PAID":
            processing_status = "ignored_out_of_order"
        elif isinstance(payment_entity, dict) and provider_payment_id:
            amount_minor = int(payment_entity.get("amount") or po.amount_minor)
            currency = str(payment_entity.get("currency") or po.currency).upper()
            method = payment_entity.get("method")
            if po.status != "CAPTURED":
                po.status = "AUTHORIZED"
                po.updated_at = now
                order.payment_status = "AUTHORIZED"
                order.updated_at = now
            _upsert_non_capture_attempt_and_txn(
                db,
                organisation_id=po.organisation_id,
                order=order,
                po=po,
                provider_payment_id=provider_payment_id,
                target_status="AUTHORIZED",
                amount_minor=amount_minor,
                currency=currency,
                method=method,
                metadata={
                    "provider_event_id": provider_event_id,
                    "event_type": event_type,
                },
            )
    elif event_type == "payment.failed":
        if po.status == "CAPTURED" or order.order_status == "PAID":
            processing_status = "ignored_out_of_order"
        elif isinstance(payment_entity, dict) and provider_payment_id:
            amount_minor = int(payment_entity.get("amount") or po.amount_minor)
            currency = str(payment_entity.get("currency") or po.currency).upper()
            method = payment_entity.get("method")
            err_code = payment_entity.get("error_code")
            err_desc = payment_entity.get("error_description")
            po.status = "FAILED"
            po.updated_at = now
            order.payment_status = "FAILED"
            order.updated_at = now
            _upsert_non_capture_attempt_and_txn(
                db,
                organisation_id=po.organisation_id,
                order=order,
                po=po,
                provider_payment_id=provider_payment_id,
                target_status="FAILED",
                amount_minor=amount_minor,
                currency=currency,
                method=method,
                failure_code=err_code,
                failure_reason=err_desc,
                metadata={
                    "provider_event_id": provider_event_id,
                    "event_type": event_type,
                },
            )
            db.add(
                OrderEvent(
                    organisation_id=po.organisation_id,
                    order_id=order.id,
                    from_status=order.order_status,
                    to_status=order.order_status,
                    event_type="payment_failed",
                    actor_ref="webhook:razorpay",
                    details={
                        "provider_event_id": provider_event_id,
                        "provider_payment_id": provider_payment_id,
                        "error_code": err_code,
                    },
                )
            )
    else:
        processing_status = "processed"

    event_row.processing_status = processing_status
    event_row.processed_at = now
    db.add(
        AuditLog(
            organisation_id=po.organisation_id,
            actor_type="webhook",
            actor_ref="razorpay",
            action=f"webhook_{event_type}",
            entity_name="payment_webhook_events",
            entity_id=str(event_row.id),
            details={
                "provider_event_id": provider_event_id,
                "processing_status": processing_status,
                "provider_order_id": provider_order_id,
                "provider_payment_id": provider_payment_id,
            },
        )
    )
    db.commit()
    return {
        "status": processing_status,
        "event_type": event_type,
        "provider_event_id": provider_event_id,
    }
