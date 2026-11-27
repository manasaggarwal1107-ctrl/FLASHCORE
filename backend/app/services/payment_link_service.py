from datetime import datetime, timedelta, timezone
import uuid

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.auth_dependencies import OrgContext
from app.models.finance import PaymentLink
from app.models.payments import PaymentOrder, PaymentProviderAccount
from app.models.retail import Customer, Order
from app.models.rossmann import AuditLog
from app.schemas.finance import PaymentLinkCreateRequest, PaymentLinkOut
from app.schemas.retail import format_minor_to_decimal_str
from app.services import payment_service
from app.services.payments import (
    GatewayPaymentLinkRequest,
    GatewayTimeoutError,
    PaymentGatewayError,
)


def _to_link_out(link: PaymentLink) -> PaymentLinkOut:
    return PaymentLinkOut(
        id=str(link.id),
        organisation_id=link.organisation_id,
        order_id=str(link.order_id),
        customer_id=link.customer_id,
        provider=link.provider,
        provider_link_id=link.provider_link_id,
        reference_id=link.reference_id,
        amount_minor=link.amount_minor,
        amount=format_minor_to_decimal_str(link.amount_minor),
        amount_paid_minor=link.amount_paid_minor,
        amount_paid=format_minor_to_decimal_str(link.amount_paid_minor),
        currency=link.currency,
        accept_partial=link.accept_partial,
        description=link.description,
        customer_name=link.customer_name,
        customer_email=link.customer_email,
        customer_phone=link.customer_phone,
        short_url=link.short_url,
        status=link.status,
        expires_at=link.expires_at,
        paid_at=link.paid_at,
        cancelled_at=link.cancelled_at,
        created_at=link.created_at,
        updated_at=link.updated_at,
    )


def _apply_verified_link_payment_capture(
    db: Session,
    *,
    link: PaymentLink,
    account: PaymentProviderAccount,
    creds,
    adapter,
    raw_payload: dict | None,
    source: str,
    actor_ref: str,
) -> None:
    """Confirm order payment only when gateway payment entity is verified as captured."""
    order = db.scalar(
        select(Order)
        .where(
            Order.id == link.order_id,
            Order.organisation_id == link.organisation_id,
        )
        .with_for_update()
    )
    if order is None or order.order_status == "PAID":
        return

    payment_id: str | None = None
    if isinstance(raw_payload, dict):
        payments = raw_payload.get("payments")
        if isinstance(payments, list):
            for entry in payments:
                if isinstance(entry, dict) and entry.get("payment_id"):
                    payment_id = str(entry["payment_id"])
                    break
        if not payment_id and raw_payload.get("payment_id"):
            payment_id = str(raw_payload["payment_id"])

    if not payment_id:
        return

    gw_payment = adapter.fetch_payment(payment_id, creds)
    if (
        gw_payment.status.lower() != "captured"
        or gw_payment.amount_minor != order.total_minor
        or gw_payment.currency.upper() != order.currency.upper()
    ):
        return

    provider_order_id = gw_payment.provider_order_id or f"plink_ord_{link.provider_link_id}"
    po = db.scalar(
        select(PaymentOrder)
        .where(
            PaymentOrder.provider == link.provider,
            PaymentOrder.provider_order_id == provider_order_id,
        )
        .with_for_update()
    )
    if po is None:
        po = PaymentOrder(
            organisation_id=link.organisation_id,
            order_id=order.id,
            provider_account_id=account.id,
            provider=link.provider,
            provider_order_id=provider_order_id,
            amount_minor=order.total_minor,
            currency=order.currency,
            receipt=order.order_number[:40],
            status="CREATED",
        )
        db.add(po)
        db.flush()

    payment_service.apply_verified_payment_capture(
        db,
        organisation_id=link.organisation_id,
        order=order,
        po=po,
        provider_payment_id=gw_payment.provider_payment_id,
        amount_minor=gw_payment.amount_minor,
        currency=gw_payment.currency,
        method=gw_payment.method,
        source=source,
        actor_ref=actor_ref,
        metadata={"payment_link_id": link.provider_link_id},
    )


def create_payment_link(
    db: Session,
    org_ctx: OrgContext,
    payload: PaymentLinkCreateRequest,
    *,
    idempotency_key: str | None = None,
    adapter_factory: payment_service.AdapterFactory | None = None,
) -> PaymentLinkOut:
    org_id = org_ctx.organisation.id
    cleaned_key = idempotency_key.strip() if idempotency_key and idempotency_key.strip() else None

    if cleaned_key:
        existing = db.scalar(
            select(PaymentLink).where(
                PaymentLink.organisation_id == org_id,
                PaymentLink.idempotency_key == cleaned_key,
            )
        )
        if existing is not None:
            if existing.order_id != payload.order_id:
                raise HTTPException(
                    status_code=409,
                    detail="Idempotency-Key was already used for a different order.",
                )
            return _to_link_out(existing)

    order = db.scalar(
        select(Order)
        .where(Order.id == payload.order_id, Order.organisation_id == org_id)
        .with_for_update()
    )
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found.")
    if order.order_status != "PENDING_PAYMENT":
        raise HTTPException(
            status_code=409,
            detail=f"Order in status {order.order_status} is not eligible for payment link creation.",
        )

    amount_minor = payload.amount_minor if payload.amount_minor is not None else order.total_minor
    if amount_minor <= 0 or amount_minor > order.total_minor:
        raise HTTPException(
            status_code=422,
            detail="Payment link amount must be positive and cannot exceed order total.",
        )
    if amount_minor < order.total_minor and not payload.accept_partial:
        raise HTTPException(
            status_code=422,
            detail="Amount below order total requires accept_partial=true.",
        )

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

    cust = db.get(Customer, order.customer_id) if order.customer_id else None
    cust_name = payload.customer_name or (cust.name if cust else None)
    cust_email = payload.customer_email or (cust.email if cust else None)
    cust_phone = payload.customer_phone or (cust.phone if cust else None)

    reference_id = f"PL-{org_id}-{order.id}-{uuid.uuid4().hex[:8].upper()}"
    expires_at = (
        datetime.now(timezone.utc) + timedelta(hours=payload.expires_in_hours)
        if payload.expires_in_hours is not None
        else None
    )

    creds = payment_service._decrypt_credentials(account)
    adapter = (adapter_factory or payment_service.default_adapter_factory)("razorpay")
    try:
        gw_res = adapter.create_payment_link(
            GatewayPaymentLinkRequest(
                reference_id=reference_id,
                amount_minor=amount_minor,
                currency=order.currency,
                description=payload.description.strip(),
                customer_name=cust_name,
                customer_email=cust_email,
                customer_phone=cust_phone,
                accept_partial=payload.accept_partial,
                expire_by_epoch=int(expires_at.timestamp()) if expires_at else None,
                notes={
                    "organisation_id": str(org_id),
                    "order_id": str(order.id),
                    "order_number": order.order_number,
                },
            ),
            creds,
        )
    except GatewayTimeoutError as exc:
        raise HTTPException(
            status_code=504, detail="Gateway timed out creating payment link."
        ) from exc
    except PaymentGatewayError as exc:
        raise HTTPException(
            status_code=502, detail="Payment gateway failed to create payment link."
        ) from exc

    link = PaymentLink(
        organisation_id=org_id,
        order_id=order.id,
        customer_id=order.customer_id,
        provider_account_id=account.id,
        provider="razorpay",
        provider_link_id=gw_res.provider_link_id,
        reference_id=reference_id,
        idempotency_key=cleaned_key,
        amount_minor=amount_minor,
        amount_paid_minor=gw_res.amount_paid_minor,
        currency=order.currency,
        accept_partial=payload.accept_partial,
        description=payload.description.strip(),
        customer_name=cust_name,
        customer_email=cust_email,
        customer_phone=cust_phone,
        short_url=gw_res.short_url,
        status=gw_res.status,
        expires_at=gw_res.expires_at or expires_at,
        created_by_user_id=org_ctx.user.id,
    )
    db.add(link)
    db.flush()
    db.add(
        AuditLog(
            organisation_id=org_id,
            actor_type=org_ctx.membership.role,
            actor_ref=org_ctx.user.email,
            action="payment_link_created",
            entity_name="payment_links",
            entity_id=str(link.id),
            details={
                "order_id": order.id,
                "provider_link_id": link.provider_link_id,
                "amount_minor": amount_minor,
                "currency": order.currency,
            },
        )
    )
    db.commit()
    db.refresh(link)
    return _to_link_out(link)


def cancel_payment_link(
    db: Session,
    org_ctx: OrgContext,
    link_id: int,
    *,
    adapter_factory: payment_service.AdapterFactory | None = None,
) -> PaymentLinkOut:
    org_id = org_ctx.organisation.id
    link = db.scalar(
        select(PaymentLink)
        .where(PaymentLink.id == link_id, PaymentLink.organisation_id == org_id)
        .with_for_update()
    )
    if link is None:
        raise HTTPException(status_code=404, detail="Payment link not found.")
    if link.status in ("PAID", "CANCELLED", "EXPIRED"):
        raise HTTPException(
            status_code=409,
            detail=f"Payment link in status {link.status} cannot be cancelled.",
        )

    account = db.get(PaymentProviderAccount, link.provider_account_id)
    if account is None:
        raise HTTPException(status_code=409, detail="Gateway account not found.")

    creds = payment_service._decrypt_credentials(account)
    adapter = (adapter_factory or payment_service.default_adapter_factory)(link.provider)
    try:
        gw_res = adapter.cancel_payment_link(link.provider_link_id, creds)
    except GatewayTimeoutError as exc:
        raise HTTPException(
            status_code=504, detail="Gateway timed out cancelling payment link."
        ) from exc
    except PaymentGatewayError as exc:
        raise HTTPException(
            status_code=502, detail="Gateway rejected payment link cancellation."
        ) from exc

    now = datetime.now(timezone.utc)
    link.status = gw_res.status if gw_res.status == "CANCELLED" else "CANCELLED"
    link.cancelled_at = now
    link.updated_at = now
    db.add(
        AuditLog(
            organisation_id=org_id,
            actor_type=org_ctx.membership.role,
            actor_ref=org_ctx.user.email,
            action="payment_link_cancelled",
            entity_name="payment_links",
            entity_id=str(link.id),
            details={"provider_link_id": link.provider_link_id},
        )
    )
    db.commit()
    db.refresh(link)
    return _to_link_out(link)


def sync_payment_link(
    db: Session,
    org_ctx: OrgContext,
    link_id: int,
    *,
    adapter_factory: payment_service.AdapterFactory | None = None,
) -> PaymentLinkOut:
    org_id = org_ctx.organisation.id
    link = db.scalar(
        select(PaymentLink)
        .where(PaymentLink.id == link_id, PaymentLink.organisation_id == org_id)
        .with_for_update()
    )
    if link is None:
        raise HTTPException(status_code=404, detail="Payment link not found.")

    account = db.get(PaymentProviderAccount, link.provider_account_id)
    if account is None:
        raise HTTPException(status_code=409, detail="Gateway account not found.")

    creds = payment_service._decrypt_credentials(account)
    adapter = (adapter_factory or payment_service.default_adapter_factory)(link.provider)
    try:
        gw_res = adapter.fetch_payment_link(link.provider_link_id, creds)
    except GatewayTimeoutError as exc:
        raise HTTPException(
            status_code=504, detail="Gateway timed out syncing payment link."
        ) from exc
    except PaymentGatewayError as exc:
        raise HTTPException(
            status_code=502, detail="Unable to sync payment link with gateway."
        ) from exc

    now = datetime.now(timezone.utc)
    if link.status != "PAID" or gw_res.status == "PAID":
        link.status = gw_res.status
    link.amount_paid_minor = max(link.amount_paid_minor, gw_res.amount_paid_minor)
    if link.status == "PAID" and link.paid_at is None:
        link.paid_at = now
        _apply_verified_link_payment_capture(
            db,
            link=link,
            account=account,
            creds=creds,
            adapter=adapter,
            raw_payload=gw_res.raw_payload,
            source="checkout_verify",
            actor_ref=org_ctx.user.email,
        )
    link.updated_at = now
    db.commit()
    db.refresh(link)
    return _to_link_out(link)


def list_payment_links(
    db: Session,
    org_id: int,
    *,
    page: int = 1,
    page_size: int = 25,
    status: str | None = None,
) -> dict:
    query = select(PaymentLink).where(PaymentLink.organisation_id == org_id)
    count_q = select(func.count(PaymentLink.id)).where(
        PaymentLink.organisation_id == org_id
    )
    if status:
        norm = status.strip().upper()
        query = query.where(PaymentLink.status == norm)
        count_q = count_q.where(PaymentLink.status == norm)

    total = db.scalar(count_q) or 0
    offset = (page - 1) * page_size
    rows = list(
        db.scalars(
            query.order_by(PaymentLink.id.desc()).offset(offset).limit(page_size)
        ).all()
    )
    return {
        "items": [_to_link_out(r) for r in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


def get_payment_link(db: Session, org_id: int, link_id: int) -> PaymentLinkOut:
    link = db.scalar(
        select(PaymentLink).where(
            PaymentLink.id == link_id, PaymentLink.organisation_id == org_id
        )
    )
    if link is None:
        raise HTTPException(status_code=404, detail="Payment link not found.")
    return _to_link_out(link)
