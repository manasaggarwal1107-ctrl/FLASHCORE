import hashlib
import json
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.finance import PaymentRefund, PaymentRefundEvent
from app.models.payments import (
    PaymentAttempt,
    PaymentOrder,
    PaymentProviderAccount,
    PaymentTransaction,
    PaymentWebhookEvent,
)
from app.services.payments.razorpay_adapter import normalize_razorpay_refund_status
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


def _validate_webhook_payment_financials(
    payment_entity: object,
    po: PaymentOrder,
) -> tuple[str, int, str]:
    if not isinstance(payment_entity, dict):
        raise ValueError("Webhook payload missing payment entity.")

    raw_pid = payment_entity.get("id")
    if not isinstance(raw_pid, str) or not raw_pid.strip():
        raise ValueError("Webhook payment entity missing valid provider payment ID.")
    provider_payment_id = raw_pid.strip()

    if "amount" not in payment_entity or payment_entity["amount"] is None:
        raise ValueError("Webhook payment entity missing amount.")
    raw_amount = payment_entity["amount"]
    if isinstance(raw_amount, bool) or not isinstance(raw_amount, int):
        raise ValueError("Webhook payment amount must be an integer in minor units.")
    if raw_amount <= 0:
        raise ValueError("Webhook payment amount must be a positive integer.")

    raw_currency = payment_entity.get("currency")
    if not isinstance(raw_currency, str) or not raw_currency.strip():
        raise ValueError("Webhook payment entity missing currency.")
    currency = raw_currency.strip().upper()
    if len(currency) != 3 or not currency.isascii() or not currency.isalpha():
        raise ValueError("Webhook payment currency format is invalid.")

    if raw_amount != po.amount_minor or currency != po.currency.upper():
        raise ValueError(
            "Webhook payment amount or currency does not match expected payment order."
        )

    return provider_payment_id, raw_amount, currency


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


def _process_razorpay_refund_webhook(
    db: Session,
    *,
    payload: dict,
    raw_body: bytes,
    signature: str,
    header_event_id: str | None,
    event_type: str,
    payload_hash: str,
) -> dict:
    inner = payload.get("payload") or {}
    refund_entity = (inner.get("refund") or {}).get("entity")
    if not isinstance(refund_entity, dict):
        raise HTTPException(
            status_code=400, detail="Webhook payload missing refund entity."
        )

    raw_refund_id = refund_entity.get("id")
    raw_payment_id = refund_entity.get("payment_id")
    if not isinstance(raw_refund_id, str) or not raw_refund_id.strip():
        raise HTTPException(status_code=400, detail="Webhook missing refund ID.")
    provider_refund_id = raw_refund_id.strip()
    provider_payment_id = (
        raw_payment_id.strip()
        if isinstance(raw_payment_id, str) and raw_payment_id.strip()
        else None
    )

    refund = db.scalar(
        select(PaymentRefund)
        .where(
            PaymentRefund.provider == "razorpay",
            PaymentRefund.provider_refund_id == provider_refund_id,
        )
        .with_for_update()
    )
    if refund is None:
        raise HTTPException(status_code=404, detail="Unknown refund for webhook.")

    po = db.get(PaymentOrder, refund.payment_order_id)
    account = (
        db.get(PaymentProviderAccount, po.provider_account_id)
        if po is not None
        else None
    )
    if account is None:
        raise HTTPException(
            status_code=404, detail="Gateway account for refund not found."
        )

    provider_event_id = (
        header_event_id.strip()[:120]
        if header_event_id and header_event_id.strip()
        else hashlib.sha256(
            f"{event_type}:{provider_refund_id}:{payload_hash[:12]}".encode("utf-8")
        ).hexdigest()[:64]
    )
    sanitized = {
        "event": event_type,
        "provider_refund_id": provider_refund_id,
        "provider_payment_id": provider_payment_id,
        "amount": refund_entity.get("amount"),
        "currency": refund_entity.get("currency"),
        "status": refund_entity.get("status"),
    }

    creds = _decrypt_credentials(account)
    adapter = default_adapter_factory("razorpay")
    now = datetime.now(timezone.utc)
    if not adapter.verify_webhook(raw_body, signature, creds.webhook_secret):
        existing_rej = db.scalar(
            select(PaymentWebhookEvent).where(
                PaymentWebhookEvent.provider == "razorpay",
                PaymentWebhookEvent.provider_event_id == provider_event_id,
            )
        )
        if existing_rej is None:
            db.add(
                PaymentWebhookEvent(
                    organisation_id=refund.organisation_id,
                    provider_account_id=account.id,
                    provider="razorpay",
                    provider_event_id=provider_event_id,
                    event_type=event_type,
                    provider_order_id=po.provider_order_id if po else None,
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
    if existing_event is not None:
        if existing_event.processing_status == "failed":
            raise HTTPException(
                status_code=422,
                detail=existing_event.error_message
                or "Malformed refund webhook payload.",
            )
        return {
            "status": "ignored_duplicate",
            "event_type": event_type,
            "provider_event_id": provider_event_id,
        }

    event_row = PaymentWebhookEvent(
        organisation_id=refund.organisation_id,
        provider_account_id=account.id,
        provider="razorpay",
        provider_event_id=provider_event_id,
        event_type=event_type,
        provider_order_id=po.provider_order_id if po else None,
        provider_payment_id=provider_payment_id,
        signature_valid=True,
        processing_status="received",
        payload_hash=payload_hash,
        sanitized_summary=sanitized,
    )
    db.add(event_row)
    db.flush()

    raw_amount = refund_entity.get("amount")
    raw_currency = refund_entity.get("currency")
    if (
        isinstance(raw_amount, bool)
        or not isinstance(raw_amount, int)
        or raw_amount <= 0
        or not isinstance(raw_currency, str)
        or raw_amount != refund.amount_minor
        or raw_currency.strip().upper() != refund.currency.upper()
    ):
        err_msg = "Refund webhook amount or currency is missing, malformed, or mismatched."
        event_row.processing_status = "failed"
        event_row.error_message = err_msg
        event_row.processed_at = now
        db.commit()
        raise HTTPException(status_code=422, detail=err_msg)

    target_status = normalize_razorpay_refund_status(
        refund_entity.get("status")
        or (
            "processed"
            if event_type == "refund.processed"
            else "failed"
            if event_type == "refund.failed"
            else "pending"
        )
    )
    prev_status = refund.status
    if prev_status == "PROCESSED" and target_status != "PROCESSED":
        event_row.processing_status = "ignored_out_of_order"
    else:
        refund.status = target_status
        refund.provider_status = str(refund_entity.get("status") or target_status.lower())
        if target_status == "PROCESSED" and refund.processed_at is None:
            refund.processed_at = now
        refund.updated_at = now
        db.add(
            PaymentRefundEvent(
                organisation_id=refund.organisation_id,
                refund_id=refund.id,
                from_status=prev_status,
                to_status=target_status,
                event_type=f"webhook_{event_type}",
                source="webhook",
                actor_ref="webhook:razorpay",
                details={"provider_event_id": provider_event_id},
            )
        )
        event_row.processing_status = "processed"

    event_row.processed_at = now
    db.add(
        AuditLog(
            organisation_id=refund.organisation_id,
            actor_type="webhook",
            actor_ref="razorpay",
            action=f"webhook_{event_type}",
            entity_name="payment_refunds",
            entity_id=str(refund.id),
            details={
                "provider_event_id": provider_event_id,
                "processing_status": event_row.processing_status,
                "provider_refund_id": provider_refund_id,
            },
        )
    )
    db.commit()
    return {
        "status": event_row.processing_status,
        "event_type": event_type,
        "provider_event_id": provider_event_id,
    }


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

    if event_type.startswith("refund."):
        return _process_razorpay_refund_webhook(
            db,
            payload=payload,
            raw_body=raw_body,
            signature=signature,
            header_event_id=header_event_id,
            event_type=event_type,
            payload_hash=payload_hash,
        )

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
    if existing_event is not None:
        if existing_event.processing_status in (
            "processed",
            "ignored_duplicate",
            "ignored_out_of_order",
        ):
            return {
                "status": "ignored_duplicate",
                "event_type": event_type,
                "provider_event_id": provider_event_id,
            }
        if existing_event.processing_status == "failed":
            raise HTTPException(
                status_code=422,
                detail=existing_event.error_message
                or "Malformed webhook financial payload.",
            )

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
    financial_events = (
        "payment.captured",
        "order.paid",
        "payment.authorized",
        "payment.failed",
    )

    if event_type in financial_events:
        try:
            validated_pid, amount_minor, currency = _validate_webhook_payment_financials(
                payment_entity, po
            )
        except ValueError as exc:
            err_msg = str(exc)
            event_row.processing_status = "failed"
            event_row.error_message = err_msg
            event_row.processed_at = now
            db.add(
                AuditLog(
                    organisation_id=po.organisation_id,
                    actor_type="webhook",
                    actor_ref="razorpay",
                    action=f"webhook_{event_type}_validation_failed",
                    entity_name="payment_webhook_events",
                    entity_id=str(event_row.id),
                    details={
                        "provider_event_id": provider_event_id,
                        "provider_order_id": provider_order_id,
                        "provider_payment_id": provider_payment_id,
                        "error": err_msg,
                    },
                )
            )
            db.commit()
            raise HTTPException(status_code=422, detail=err_msg) from exc

        method = payment_entity.get("method") if isinstance(payment_entity, dict) else None

        if event_type in ("payment.captured", "order.paid"):
            if po.status == "CAPTURED" and order.order_status == "PAID":
                processing_status = "ignored_duplicate"
            else:
                newly_captured = apply_verified_payment_capture(
                    db,
                    organisation_id=po.organisation_id,
                    order=order,
                    po=po,
                    provider_payment_id=validated_pid,
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
            else:
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
                    provider_payment_id=validated_pid,
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
            else:
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
                    provider_payment_id=validated_pid,
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
                            "provider_payment_id": validated_pid,
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
