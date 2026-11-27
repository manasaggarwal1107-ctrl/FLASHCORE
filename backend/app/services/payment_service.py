from datetime import datetime, timezone
from typing import Callable

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.auth_dependencies import OrgContext
from app.core.crypto import decrypt_secret, encrypt_secret
from app.models.payments import (
    PaymentAttempt,
    PaymentOrder,
    PaymentProviderAccount,
    PaymentTransaction,
)
from app.models.retail import Order, OrderEvent
from app.models.rossmann import AuditLog
from app.schemas.payments import (
    GatewayAccountOut,
    GatewayAccountUpsert,
    PaymentOrderOut,
    PaymentTransactionOut,
    PaymentVerificationOut,
    PaymentVerifyRequest,
)
from app.schemas.retail import format_minor_to_decimal_str
from app.services import inventory_service
from app.services.payments import (
    CheckoutSignatureInput,
    GatewayCredentials,
    GatewayOrderRequest,
    PaymentGatewayAdapter,
    RazorpayAdapter,
)

AdapterFactory = Callable[[str], PaymentGatewayAdapter]


def default_adapter_factory(provider: str) -> PaymentGatewayAdapter:
    if provider == "razorpay":
        return RazorpayAdapter()
    raise HTTPException(
        status_code=400, detail=f"Unsupported payment provider: {provider}"
    )


def _account_aad(organisation_id: int, provider: str) -> str:
    return f"org:{organisation_id}:provider:{provider}"


def _decrypt_credentials(account: PaymentProviderAccount) -> GatewayCredentials:
    aad = _account_aad(account.organisation_id, account.provider)
    return GatewayCredentials(
        provider=account.provider,
        mode=account.mode,
        key_id=account.key_id,
        key_secret=decrypt_secret(account.encrypted_key_secret, aad=aad),
        webhook_secret=decrypt_secret(account.encrypted_webhook_secret, aad=aad),
    )


def _to_account_out(account: PaymentProviderAccount) -> GatewayAccountOut:
    return GatewayAccountOut(
        id=account.id,
        organisation_id=account.organisation_id,
        provider=account.provider,
        mode=account.mode,
        key_id=account.key_id,
        status=account.status,
        has_key_secret=bool(account.encrypted_key_secret),
        has_webhook_secret=bool(account.encrypted_webhook_secret),
        created_at=account.created_at,
        updated_at=account.updated_at,
    )


def upsert_razorpay_account(
    db: Session, org_ctx: OrgContext, payload: GatewayAccountUpsert
) -> GatewayAccountOut:
    if payload.mode != "test":
        raise HTTPException(
            status_code=422,
            detail="Live Razorpay mode is disabled in Stage 3; test mode only.",
        )
    if not payload.key_id.startswith("rzp_test_"):
        raise HTTPException(
            status_code=422,
            detail="Test-mode Razorpay Key ID must start with 'rzp_test_'.",
        )

    org_id = org_ctx.organisation.id
    aad = _account_aad(org_id, "razorpay")
    enc_secret = encrypt_secret(payload.key_secret, aad=aad, key_version="v1")
    enc_webhook = encrypt_secret(payload.webhook_secret, aad=aad, key_version="v1")

    account = db.scalar(
        select(PaymentProviderAccount).where(
            PaymentProviderAccount.organisation_id == org_id,
            PaymentProviderAccount.provider == "razorpay",
            PaymentProviderAccount.mode == "test",
        )
    )
    now = datetime.now(timezone.utc)
    if account is None:
        account = PaymentProviderAccount(
            organisation_id=org_id,
            provider="razorpay",
            mode="test",
            key_id=payload.key_id,
            encrypted_key_secret=enc_secret,
            encrypted_webhook_secret=enc_webhook,
            key_version="v1",
            status=payload.status,
        )
        db.add(account)
    else:
        account.key_id = payload.key_id
        account.encrypted_key_secret = enc_secret
        account.encrypted_webhook_secret = enc_webhook
        account.status = payload.status
        account.updated_at = now

    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="This Razorpay Key ID is already registered to another account.",
        ) from exc

    db.add(
        AuditLog(
            organisation_id=org_id,
            actor_type=org_ctx.membership.role,
            actor_ref=org_ctx.user.email,
            action="payment_gateway_account_saved",
            entity_name="payment_provider_accounts",
            entity_id=str(account.id),
            details={
                "provider": "razorpay",
                "mode": "test",
                "key_id": account.key_id,
                "status": "success",
            },
        )
    )
    db.commit()
    db.refresh(account)
    return _to_account_out(account)


def list_gateway_accounts(db: Session, org_id: int) -> list[GatewayAccountOut]:
    rows = list(
        db.scalars(
            select(PaymentProviderAccount)
            .where(PaymentProviderAccount.organisation_id == org_id)
            .order_by(PaymentProviderAccount.id.asc())
        ).all()
    )
    return [_to_account_out(r) for r in rows]


def _to_payment_order_out(
    po: PaymentOrder, account: PaymentProviderAccount, order: Order
) -> PaymentOrderOut:
    prefill = None
    if isinstance(order.customer_snapshot, dict):
        prefill = {
            "name": order.customer_snapshot.get("name"),
            "email": order.customer_snapshot.get("email"),
            "contact": order.customer_snapshot.get("phone"),
        }
    return PaymentOrderOut(
        id=str(po.id),
        organisation_id=po.organisation_id,
        order_id=str(po.order_id),
        provider=po.provider,
        mode=account.mode,
        provider_order_id=po.provider_order_id,
        key_id=account.key_id,
        amount_minor=po.amount_minor,
        amount=format_minor_to_decimal_str(po.amount_minor),
        currency=po.currency,
        receipt=po.receipt,
        status=po.status,
        prefill=prefill,
        created_at=po.created_at,
        updated_at=po.updated_at,
    )


def create_payment_order_for_checkout(
    db: Session,
    org_ctx: OrgContext,
    order_id: int,
    *,
    idempotency_key: str | None = None,
    adapter_factory: AdapterFactory | None = None,
) -> PaymentOrderOut:
    org_id = org_ctx.organisation.id
    cleaned_key = idempotency_key.strip() if idempotency_key else None

    if cleaned_key:
        existing_po = db.scalar(
            select(PaymentOrder).where(
                PaymentOrder.organisation_id == org_id,
                PaymentOrder.idempotency_key == cleaned_key,
            )
        )
        if existing_po is not None:
            if existing_po.order_id != order_id:
                raise HTTPException(
                    status_code=409,
                    detail="Idempotency-Key was already used for a different order.",
                )
            account = db.get(PaymentProviderAccount, existing_po.provider_account_id)
            order = db.get(Order, existing_po.order_id)
            return _to_payment_order_out(existing_po, account, order)

    inventory_service.expire_stale_reservations(
        db, organisation_id=org_id, actor_ref=org_ctx.user.email
    )

    order = db.scalar(
        select(Order)
        .where(Order.id == order_id, Order.organisation_id == org_id)
        .with_for_update()
    )
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found.")

    if order.order_status != "PENDING_PAYMENT":
        raise HTTPException(
            status_code=409,
            detail=f"Order in status {order.order_status} is not eligible for checkout.",
        )

    if order.total_minor <= 0:
        raise HTTPException(
            status_code=422, detail="Payable order total must be greater than zero."
        )

    # Reuse active CREATED/PENDING payment order for this order if one exists
    reusable_po = db.scalar(
        select(PaymentOrder)
        .where(
            PaymentOrder.organisation_id == org_id,
            PaymentOrder.order_id == order.id,
            PaymentOrder.status.in_(("CREATED", "PENDING")),
        )
        .order_by(PaymentOrder.id.desc())
    )
    if reusable_po is not None and reusable_po.amount_minor == order.total_minor:
        account = db.get(PaymentProviderAccount, reusable_po.provider_account_id)
        return _to_payment_order_out(reusable_po, account, order)

    account = db.scalar(
        select(PaymentProviderAccount).where(
            PaymentProviderAccount.organisation_id == org_id,
            PaymentProviderAccount.provider == "razorpay",
            PaymentProviderAccount.mode == "test",
            PaymentProviderAccount.status == "active",
        )
    )
    if account is None:
        raise HTTPException(
            status_code=409,
            detail="No active test-mode Razorpay gateway account is configured for this organisation.",
        )

    creds = _decrypt_credentials(account)
    adapter = (adapter_factory or default_adapter_factory)(account.provider)
    receipt = order.order_number[:40]
    try:
        gw_result = adapter.create_order(
            GatewayOrderRequest(
                amount_minor=order.total_minor,
                currency=order.currency,
                receipt=receipt,
                notes={
                    "organisation_id": str(org_id),
                    "order_id": str(order.id),
                    "order_number": order.order_number,
                },
            ),
            creds,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail="Payment gateway order creation failed.",
        ) from exc

    po = PaymentOrder(
        organisation_id=org_id,
        order_id=order.id,
        provider_account_id=account.id,
        provider=account.provider,
        provider_order_id=gw_result.provider_order_id,
        idempotency_key=cleaned_key,
        amount_minor=order.total_minor,
        currency=order.currency,
        receipt=gw_result.receipt,
        status="CREATED",
        provider_payload=gw_result.raw_payload,
    )
    db.add(po)
    order.payment_status = "CREATED"
    order.updated_at = datetime.now(timezone.utc)
    db.flush()

    db.add(
        AuditLog(
            organisation_id=org_id,
            actor_type=org_ctx.membership.role,
            actor_ref=org_ctx.user.email,
            action="payment_order_created",
            entity_name="payment_orders",
            entity_id=str(po.id),
            details={
                "order_id": order.id,
                "provider": po.provider,
                "provider_order_id": po.provider_order_id,
                "amount_minor": po.amount_minor,
                "currency": po.currency,
                "status": "success",
            },
        )
    )
    db.commit()
    db.refresh(po)
    return _to_payment_order_out(po, account, order)


def apply_verified_payment_capture(
    db: Session,
    *,
    organisation_id: int,
    order: Order,
    po: PaymentOrder,
    provider_payment_id: str,
    amount_minor: int,
    currency: str,
    method: str | None,
    source: str,
    actor_ref: str,
    metadata: dict | None = None,
) -> bool:
    """Idempotently capture a verified payment and confirm order reservations.

    Returns True if newly captured, False if already captured (idempotent replay).
    """
    if po.status == "CAPTURED" and order.order_status == "PAID":
        return False

    if amount_minor != po.amount_minor or currency.upper() != po.currency.upper():
        raise HTTPException(
            status_code=409,
            detail="Payment amount or currency does not match payment order.",
        )

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
            status="CAPTURED",
            signature_verified=True,
        )
        db.add(attempt)
        db.flush()
    else:
        attempt.status = "CAPTURED"
        attempt.signature_verified = True
        attempt.updated_at = now

    existing_txn = db.scalar(
        select(PaymentTransaction).where(
            PaymentTransaction.provider == po.provider,
            PaymentTransaction.provider_payment_id == provider_payment_id,
            PaymentTransaction.event_type == "CAPTURED",
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
                event_type="CAPTURED",
                amount_minor=amount_minor,
                currency=currency.upper(),
                status="CAPTURED",
                method=method,
                source=source,
                metadata_json=metadata,
            )
        )

    po.status = "CAPTURED"
    po.updated_at = now

    prev_order_status = order.order_status
    order.payment_status = "CAPTURED"
    if order.order_status == "PENDING_PAYMENT":
        inventory_service.confirm_order_reservations(
            db,
            organisation_id=organisation_id,
            order_id=order.id,
            actor_ref=actor_ref,
        )
        order.order_status = "PAID"
        db.add(
            OrderEvent(
                organisation_id=organisation_id,
                order_id=order.id,
                from_status=prev_order_status,
                to_status="PAID",
                event_type="payment_captured",
                actor_ref=actor_ref,
                details={
                    "provider": po.provider,
                    "provider_order_id": po.provider_order_id,
                    "provider_payment_id": provider_payment_id,
                    "source": source,
                },
            )
        )
    order.updated_at = now
    return True


def verify_checkout_payment(
    db: Session,
    org_ctx: OrgContext,
    payment_order_id: int,
    payload: PaymentVerifyRequest,
    *,
    adapter_factory: AdapterFactory | None = None,
) -> PaymentVerificationOut:
    org_id = org_ctx.organisation.id
    po = db.scalar(
        select(PaymentOrder)
        .where(
            PaymentOrder.id == payment_order_id,
            PaymentOrder.organisation_id == org_id,
        )
        .with_for_update()
    )
    if po is None:
        raise HTTPException(status_code=404, detail="Payment order not found.")

    order = db.scalar(
        select(Order)
        .where(Order.id == po.order_id, Order.organisation_id == org_id)
        .with_for_update()
    )
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found.")

    if payload.razorpay_order_id != po.provider_order_id:
        raise HTTPException(
            status_code=400,
            detail="Provider order ID does not match payment order.",
        )

    account = db.get(PaymentProviderAccount, po.provider_account_id)
    if account is None or account.organisation_id != org_id:
        raise HTTPException(status_code=409, detail="Gateway account not found.")

    creds = _decrypt_credentials(account)
    adapter = (adapter_factory or default_adapter_factory)(po.provider)

    sig_ok = adapter.verify_checkout_signature(
        CheckoutSignatureInput(
            provider_order_id=payload.razorpay_order_id,
            provider_payment_id=payload.razorpay_payment_id,
            signature=payload.razorpay_signature,
        ),
        creds,
    )
    if not sig_ok:
        db.add(
            AuditLog(
                organisation_id=org_id,
                actor_type=org_ctx.membership.role,
                actor_ref=org_ctx.user.email,
                action="payment_signature_rejected",
                entity_name="payment_orders",
                entity_id=str(po.id),
                details={
                    "provider_order_id": po.provider_order_id,
                    "provider_payment_id": payload.razorpay_payment_id,
                    "status": "failed",
                },
            )
        )
        db.commit()
        raise HTTPException(status_code=400, detail="Invalid payment signature.")

    # Idempotent replay check before calling gateway API if already captured
    if po.status == "CAPTURED" and order.order_status == "PAID":
        return PaymentVerificationOut(
            verified=True,
            payment_order_id=str(po.id),
            order_id=str(order.id),
            order_status=order.order_status,
            payment_status=order.payment_status,
            provider_order_id=po.provider_order_id,
            provider_payment_id=payload.razorpay_payment_id,
            amount_minor=po.amount_minor,
            amount=format_minor_to_decimal_str(po.amount_minor),
            currency=po.currency,
            idempotent_replay=True,
        )

    # Independently fetch payment from Razorpay to verify status, amount, currency & order linkage
    try:
        gw_payment = adapter.fetch_payment(payload.razorpay_payment_id, creds)
    except Exception as exc:
        raise HTTPException(
            status_code=502, detail="Unable to verify payment status with gateway."
        ) from exc

    if (
        not isinstance(gw_payment.provider_order_id, str)
        or not gw_payment.provider_order_id.strip()
        or gw_payment.provider_order_id.strip() != po.provider_order_id
    ):
        db.add(
            AuditLog(
                organisation_id=org_id,
                actor_type=org_ctx.membership.role,
                actor_ref=org_ctx.user.email,
                action="payment_order_linkage_rejected",
                entity_name="payment_orders",
                entity_id=str(po.id),
                details={
                    "order_id": order.id,
                    "expected_provider_order_id": po.provider_order_id,
                    "gateway_provider_order_id": gw_payment.provider_order_id,
                    "provider_payment_id": gw_payment.provider_payment_id,
                    "status": "rejected",
                },
            )
        )
        db.commit()
        raise HTTPException(
            status_code=409,
            detail="Gateway payment order reference is missing or does not match the expected payment order.",
        )

    if gw_payment.amount_minor != po.amount_minor or gw_payment.currency.upper() != po.currency.upper():
        raise HTTPException(
            status_code=409,
            detail="Gateway payment amount or currency mismatch.",
        )

    gw_status = gw_payment.status.lower()
    now = datetime.now(timezone.utc)

    if gw_status == "captured":
        newly_captured = apply_verified_payment_capture(
            db,
            organisation_id=org_id,
            order=order,
            po=po,
            provider_payment_id=gw_payment.provider_payment_id,
            amount_minor=gw_payment.amount_minor,
            currency=gw_payment.currency,
            method=gw_payment.method,
            source="checkout_verify",
            actor_ref=org_ctx.user.email,
            metadata={"gateway_status": gw_status},
        )
        db.add(
            AuditLog(
                organisation_id=org_id,
                actor_type=org_ctx.membership.role,
                actor_ref=org_ctx.user.email,
                action="payment_verified_captured",
                entity_name="payment_orders",
                entity_id=str(po.id),
                details={
                    "order_id": order.id,
                    "provider_payment_id": gw_payment.provider_payment_id,
                    "amount_minor": gw_payment.amount_minor,
                    "status": "success",
                },
            )
        )
        db.commit()
        return PaymentVerificationOut(
            verified=True,
            payment_order_id=str(po.id),
            order_id=str(order.id),
            order_status=order.order_status,
            payment_status=order.payment_status,
            provider_order_id=po.provider_order_id,
            provider_payment_id=gw_payment.provider_payment_id,
            amount_minor=po.amount_minor,
            amount=format_minor_to_decimal_str(po.amount_minor),
            currency=po.currency,
            idempotent_replay=not newly_captured,
        )

    if gw_status == "authorized":
        attempt = db.scalar(
            select(PaymentAttempt)
            .where(
                PaymentAttempt.provider == po.provider,
                PaymentAttempt.provider_payment_id == gw_payment.provider_payment_id,
            )
            .with_for_update()
        )
        attempt_existed = attempt is not None
        if attempt is None:
            attempt = PaymentAttempt(
                organisation_id=org_id,
                payment_order_id=po.id,
                order_id=order.id,
                provider=po.provider,
                provider_payment_id=gw_payment.provider_payment_id,
                status="AUTHORIZED",
                signature_verified=True,
            )
            db.add(attempt)
            db.flush()
        else:
            if attempt.status != "CAPTURED":
                attempt.status = "AUTHORIZED"
            attempt.signature_verified = True
            attempt.updated_at = now

        if po.status != "CAPTURED":
            po.status = "AUTHORIZED"
            po.updated_at = now
        if order.order_status != "PAID" and order.payment_status != "CAPTURED":
            order.payment_status = "AUTHORIZED"
            order.updated_at = now

        existing_auth_txn = db.scalar(
            select(PaymentTransaction).where(
                PaymentTransaction.provider == po.provider,
                PaymentTransaction.provider_payment_id == gw_payment.provider_payment_id,
                PaymentTransaction.event_type == "AUTHORIZED",
            )
        )
        txn_existed = existing_auth_txn is not None
        if existing_auth_txn is None:
            db.add(
                PaymentTransaction(
                    organisation_id=org_id,
                    order_id=order.id,
                    payment_order_id=po.id,
                    payment_attempt_id=attempt.id,
                    provider=po.provider,
                    provider_payment_id=gw_payment.provider_payment_id,
                    event_type="AUTHORIZED",
                    amount_minor=gw_payment.amount_minor,
                    currency=gw_payment.currency.upper(),
                    status="AUTHORIZED",
                    method=gw_payment.method,
                    source="checkout_verify",
                    metadata_json={"gateway_status": gw_status},
                )
            )

        is_replay = attempt_existed and txn_existed
        if not is_replay:
            db.add(
                AuditLog(
                    organisation_id=org_id,
                    actor_type=org_ctx.membership.role,
                    actor_ref=org_ctx.user.email,
                    action="payment_verified_authorized",
                    entity_name="payment_orders",
                    entity_id=str(po.id),
                    details={
                        "order_id": order.id,
                        "provider_payment_id": gw_payment.provider_payment_id,
                        "amount_minor": gw_payment.amount_minor,
                        "status": "authorized",
                    },
                )
            )
        db.commit()
        return PaymentVerificationOut(
            verified=True,
            payment_order_id=str(po.id),
            order_id=str(order.id),
            order_status=order.order_status,
            payment_status=order.payment_status,
            provider_order_id=po.provider_order_id,
            provider_payment_id=gw_payment.provider_payment_id,
            amount_minor=po.amount_minor,
            amount=format_minor_to_decimal_str(po.amount_minor),
            currency=po.currency,
            idempotent_replay=is_replay,
        )

    # Failed / created / unpaid gateway state: do NOT mark order PAID
    po.status = "FAILED" if gw_status == "failed" else "PENDING"
    po.updated_at = now
    order.payment_status = po.status
    order.updated_at = now
    db.commit()
    raise HTTPException(
        status_code=409,
        detail=f"Gateway payment is in '{gw_status}' state and not captured.",
    )


def get_payment_order(db: Session, org_id: int, payment_order_id: int) -> PaymentOrderOut:
    po = db.scalar(
        select(PaymentOrder).where(
            PaymentOrder.id == payment_order_id,
            PaymentOrder.organisation_id == org_id,
        )
    )
    if po is None:
        raise HTTPException(status_code=404, detail="Payment order not found.")
    account = db.get(PaymentProviderAccount, po.provider_account_id)
    order = db.get(Order, po.order_id)
    return _to_payment_order_out(po, account, order)


def list_payment_transactions(
    db: Session,
    org_id: int,
    *,
    page: int = 1,
    page_size: int = 25,
    status: str | None = None,
) -> dict:
    query = select(PaymentTransaction).where(
        PaymentTransaction.organisation_id == org_id
    )
    count_q = select(func.count(PaymentTransaction.id)).where(
        PaymentTransaction.organisation_id == org_id
    )
    if status:
        norm = status.strip().upper()
        query = query.where(PaymentTransaction.status == norm)
        count_q = count_q.where(PaymentTransaction.status == norm)

    total = db.scalar(count_q) or 0
    offset = (page - 1) * page_size
    rows = list(
        db.scalars(
            query.order_by(PaymentTransaction.id.desc())
            .offset(offset)
            .limit(page_size)
        ).all()
    )
    items = [
        PaymentTransactionOut(
            id=str(t.id),
            organisation_id=t.organisation_id,
            order_id=str(t.order_id),
            payment_order_id=str(t.payment_order_id),
            provider=t.provider,
            provider_payment_id=t.provider_payment_id,
            event_type=t.event_type,
            amount_minor=t.amount_minor,
            amount=format_minor_to_decimal_str(t.amount_minor),
            currency=t.currency,
            status=t.status,
            method=t.method,
            source=t.source,
            created_at=t.created_at,
        )
        for t in rows
    ]
    return {"items": items, "total": total, "page": page, "page_size": page_size}


def get_payment_transaction(
    db: Session, org_id: int, transaction_id: int
) -> PaymentTransactionOut:
    t = db.scalar(
        select(PaymentTransaction).where(
            PaymentTransaction.id == transaction_id,
            PaymentTransaction.organisation_id == org_id,
        )
    )
    if t is None:
        raise HTTPException(status_code=404, detail="Payment transaction not found.")
    return PaymentTransactionOut(
        id=str(t.id),
        organisation_id=t.organisation_id,
        order_id=str(t.order_id),
        payment_order_id=str(t.payment_order_id),
        provider=t.provider,
        provider_payment_id=t.provider_payment_id,
        event_type=t.event_type,
        amount_minor=t.amount_minor,
        amount=format_minor_to_decimal_str(t.amount_minor),
        currency=t.currency,
        status=t.status,
        method=t.method,
        source=t.source,
        created_at=t.created_at,
    )
