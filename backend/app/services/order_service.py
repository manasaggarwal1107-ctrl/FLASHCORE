from datetime import datetime, timedelta, timezone
import uuid

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.auth_dependencies import OrgContext
from app.models.payments import PaymentTransaction
from app.models.retail import (
    CommerceProduct,
    Customer,
    InventoryLocation,
    Order,
    OrderEvent,
    OrderItem,
)
from app.models.rossmann import AuditLog
from app.schemas.retail import (
    OrderCreate,
    OrderEventOut,
    OrderLineOut,
    OrderOut,
    OrderTransitionRequest,
    format_minor_to_decimal_str,
)
from app.services import inventory_service

VALID_ORDER_TRANSITIONS: dict[str, set[str]] = {
    "DRAFT": {"PENDING_PAYMENT", "CANCELLED", "EXPIRED"},
    "PENDING_PAYMENT": {"PAID", "CANCELLED", "EXPIRED"},
    "PAID": {"PROCESSING", "FULFILLED"},
    "PROCESSING": {"FULFILLED"},
    "FULFILLED": set(),
    "CANCELLED": set(),
    "EXPIRED": set(),
}

NON_MANUAL_TARGET_STATES = {"PAID", "EXPIRED"}


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _generate_order_number(org_id: int) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    suffix = uuid.uuid4().hex[:8].upper()
    return f"ORD-{org_id}-{stamp}-{suffix}"


def _build_order_out(db: Session, order: Order, include_events: bool = True) -> OrderOut:
    items = list(
        db.scalars(
            select(OrderItem)
            .where(
                OrderItem.order_id == order.id,
                OrderItem.organisation_id == order.organisation_id,
            )
            .order_by(OrderItem.id.asc())
        ).all()
    )
    events_out: list[OrderEventOut] | None = None
    if include_events:
        events = list(
            db.scalars(
                select(OrderEvent)
                .where(
                    OrderEvent.order_id == order.id,
                    OrderEvent.organisation_id == order.organisation_id,
                )
                .order_by(OrderEvent.id.asc())
            ).all()
        )
        events_out = [
            OrderEventOut(
                id=e.id,
                from_status=e.from_status,
                to_status=e.to_status,
                event_type=e.event_type,
                actor_ref=e.actor_ref,
                details=e.details,
                created_at=e.created_at,
            )
            for e in events
        ]

    latest_txn = db.scalar(
        select(PaymentTransaction.provider_payment_id)
        .where(
            PaymentTransaction.organisation_id == order.organisation_id,
            PaymentTransaction.order_id == order.id,
        )
        .order_by(PaymentTransaction.id.desc())
        .limit(1)
    )

    cust_ref = f"CUST-{order.customer_id:05d}" if order.customer_id else None
    cust_name = (
        order.customer_snapshot.get("name")
        if isinstance(order.customer_snapshot, dict)
        else None
    )

    lines = [
        OrderLineOut(
            id=line.id,
            product_id=str(line.product_id),
            location_id=line.location_id,
            sku=line.sku_snapshot,
            product_name=line.name_snapshot,
            quantity=line.quantity,
            unit_price_minor=line.unit_price_minor,
            unit_price=format_minor_to_decimal_str(line.unit_price_minor),
            tax_rate_bps=line.tax_rate_bps,
            tax_minor=line.tax_minor,
            line_total_minor=line.line_total_minor,
            line_total=format_minor_to_decimal_str(line.line_total_minor),
        )
        for line in items
    ]

    return OrderOut(
        id=str(order.id),
        organisation_id=order.organisation_id,
        reference=order.order_number,
        customer_id=order.customer_id,
        customer_ref=cust_ref,
        customer_name=cust_name,
        currency=order.currency,
        subtotal_minor=order.subtotal_minor,
        subtotal=format_minor_to_decimal_str(order.subtotal_minor),
        discount_minor=order.discount_minor,
        discount=format_minor_to_decimal_str(order.discount_minor),
        tax_minor=order.tax_minor,
        tax=format_minor_to_decimal_str(order.tax_minor),
        total_minor=order.total_minor,
        total=format_minor_to_decimal_str(order.total_minor),
        status=order.order_status,
        payment_status=order.payment_status,
        item_count=sum(line.quantity for line in items),
        lines=lines,
        events=events_out,
        reservation_expires_at=order.reservation_expires_at,
        transaction_ref=latest_txn,
        origin="real",
        placed_at=order.placed_at,
        created_at=order.created_at,
        updated_at=order.updated_at,
    )


def create_order(
    db: Session,
    org_ctx: OrgContext,
    payload: OrderCreate,
    *,
    idempotency_key: str | None = None,
) -> OrderOut:
    org_id = org_ctx.organisation.id

    # Expire any stale reservations first so available stock is accurate.
    inventory_service.expire_stale_reservations(
        db, organisation_id=org_id, actor_ref=org_ctx.user.email
    )

    cleaned_key = idempotency_key.strip() if idempotency_key else None
    if cleaned_key:
        existing = db.scalar(
            select(Order).where(
                Order.organisation_id == org_id,
                Order.idempotency_key == cleaned_key,
            )
        )
        if existing is not None:
            existing_items = list(
                db.scalars(
                    select(OrderItem)
                    .where(OrderItem.order_id == existing.id)
                    .order_by(OrderItem.id.asc())
                ).all()
            )
            existing_sig = sorted(
                (i.product_id, i.location_id, i.quantity) for i in existing_items
            )
            default_loc_id = (
                existing_items[0].location_id if existing_items else None
            )
            req_sig = sorted(
                (
                    item.product_id,
                    item.location_id or default_loc_id,
                    item.quantity,
                )
                for item in payload.items
            )
            if (
                existing.customer_id != payload.customer_id
                or existing.discount_minor != payload.discount_minor
                or existing_sig != req_sig
            ):
                raise HTTPException(
                    status_code=409,
                    detail="Idempotency-Key was already used with different order data.",
                )
            return _build_order_out(db, existing)

    customer_snapshot: dict | None = None
    if payload.customer_id is not None:
        customer = db.scalar(
            select(Customer).where(
                Customer.id == payload.customer_id,
                Customer.organisation_id == org_id,
            )
        )
        if customer is None:
            raise HTTPException(status_code=404, detail="Customer not found.")
        customer_snapshot = {
            "id": customer.id,
            "name": customer.name,
            "email": customer.email,
            "phone": customer.phone,
        }

    # Resolve products & locations strictly within org_id.
    default_location: InventoryLocation | None = None
    product_ids = sorted({item.product_id for item in payload.items})
    products = {
        p.id: p
        for p in db.scalars(
            select(CommerceProduct).where(
                CommerceProduct.organisation_id == org_id,
                CommerceProduct.id.in_(product_ids),
            )
        ).all()
    }
    if len(products) != len(product_ids):
        raise HTTPException(
            status_code=404,
            detail="One or more products were not found in this organisation.",
        )

    currencies = {p.currency for p in products.values()}
    if len(currencies) != 1:
        raise HTTPException(
            status_code=422,
            detail="All items in an order must share the same currency.",
        )
    currency = next(iter(currencies))

    for p in products.values():
        if p.status != "active":
            raise HTTPException(
                status_code=409,
                detail=f"Product {p.sku} is not active for ordering.",
            )

    location_ids = {
        item.location_id for item in payload.items if item.location_id is not None
    }
    locations_map: dict[int, InventoryLocation] = {}
    if location_ids:
        locs = list(
            db.scalars(
                select(InventoryLocation).where(
                    InventoryLocation.organisation_id == org_id,
                    InventoryLocation.id.in_(location_ids),
                    InventoryLocation.is_active.is_(True),
                )
            ).all()
        )
        locations_map = {loc.id: loc for loc in locs}
        if len(locations_map) != len(location_ids):
            raise HTTPException(
                status_code=404,
                detail="One or more active inventory locations were not found.",
            )

    subtotal_minor = 0
    tax_minor = 0
    resolved_lines: list[tuple[CommerceProduct, int, int, int, int]] = []

    for item in payload.items:
        product = products[item.product_id]
        if item.location_id is not None:
            loc_id = item.location_id
        else:
            if default_location is None:
                default_location = inventory_service.get_or_create_default_location(
                    db, org_id
                )
            loc_id = default_location.id

        line_sub = product.price_minor * item.quantity
        line_tax = (line_sub * product.tax_rate_bps) // 10000
        line_total = line_sub + line_tax
        subtotal_minor += line_sub
        tax_minor += line_tax
        resolved_lines.append((product, loc_id, item.quantity, line_tax, line_total))

    gross_total = subtotal_minor + tax_minor
    if payload.discount_minor > gross_total:
        raise HTTPException(
            status_code=422,
            detail="Discount cannot exceed order subtotal plus tax.",
        )
    total_minor = gross_total - payload.discount_minor

    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(minutes=payload.reservation_ttl_minutes)
    initial_status = "PENDING_PAYMENT" if payload.submit_for_payment else "DRAFT"

    order = Order(
        organisation_id=org_id,
        customer_id=payload.customer_id,
        order_number=_generate_order_number(org_id),
        idempotency_key=cleaned_key,
        currency=currency,
        subtotal_minor=subtotal_minor,
        discount_minor=payload.discount_minor,
        tax_minor=tax_minor,
        total_minor=total_minor,
        order_status=initial_status,
        payment_status="UNPAID",
        customer_snapshot=customer_snapshot,
        reservation_expires_at=expires_at if payload.submit_for_payment else None,
        placed_at=now,
    )
    db.add(order)
    db.flush()

    allocations: list[tuple[int, int, int, int]] = []
    for product, loc_id, qty, line_tax, line_total in resolved_lines:
        order_item = OrderItem(
            organisation_id=org_id,
            order_id=order.id,
            product_id=product.id,
            location_id=loc_id,
            sku_snapshot=product.sku,
            name_snapshot=product.name,
            unit_price_minor=product.price_minor,
            tax_rate_bps=product.tax_rate_bps,
            quantity=qty,
            tax_minor=line_tax,
            line_total_minor=line_total,
        )
        db.add(order_item)
        db.flush()
        allocations.append((order_item.id, product.id, loc_id, qty))

    if payload.submit_for_payment:
        inventory_service.reserve_stock_for_order(
            db,
            organisation_id=org_id,
            order_id=order.id,
            order_item_allocations=allocations,
            expires_at=expires_at,
            actor_ref=org_ctx.user.email,
        )

    db.add(
        OrderEvent(
            organisation_id=org_id,
            order_id=order.id,
            from_status=None,
            to_status=initial_status,
            event_type="order_created",
            actor_ref=org_ctx.user.email,
            details={
                "total_minor": total_minor,
                "currency": currency,
                "reserved": payload.submit_for_payment,
            },
        )
    )
    db.add(
        AuditLog(
            organisation_id=org_id,
            actor_type=org_ctx.membership.role,
            actor_ref=org_ctx.user.email,
            action="commerce_order_created",
            entity_name="orders",
            entity_id=str(order.id),
            details={
                "order_number": order.order_number,
                "order_status": initial_status,
                "total_minor": total_minor,
                "currency": currency,
                "status": "success",
            },
        )
    )
    db.commit()
    db.refresh(order)
    return _build_order_out(db, order)


def list_orders(
    db: Session,
    org_id: int,
    *,
    page: int = 1,
    page_size: int = 25,
    search: str | None = None,
    status: str | None = None,
    customer_id: int | None = None,
) -> dict:
    query = select(Order).where(Order.organisation_id == org_id)
    count_q = select(func.count(Order.id)).where(Order.organisation_id == org_id)

    if status:
        norm = status.strip().upper()
        query = query.where(Order.order_status == norm)
        count_q = count_q.where(Order.order_status == norm)
    if customer_id is not None:
        query = query.where(Order.customer_id == customer_id)
        count_q = count_q.where(Order.customer_id == customer_id)
    if search:
        pattern = f"%{_escape_like(search.strip())}%"
        filt = Order.order_number.ilike(pattern, escape="\\")
        query = query.where(filt)
        count_q = count_q.where(filt)

    total = db.scalar(count_q) or 0
    offset = (page - 1) * page_size
    orders = list(
        db.scalars(
            query.order_by(Order.id.desc()).offset(offset).limit(page_size)
        ).all()
    )
    items = [_build_order_out(db, o, include_events=False) for o in orders]
    return {"items": items, "total": total, "page": page, "page_size": page_size}


def get_order(db: Session, org_id: int, order_id: int) -> OrderOut:
    order = db.scalar(
        select(Order).where(Order.id == order_id, Order.organisation_id == org_id)
    )
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found.")
    return _build_order_out(db, order, include_events=True)


def transition_order(
    db: Session,
    org_ctx: OrgContext,
    order_id: int,
    payload: OrderTransitionRequest,
) -> OrderOut:
    org_id = org_ctx.organisation.id
    order = db.scalar(
        select(Order)
        .where(Order.id == order_id, Order.organisation_id == org_id)
        .with_for_update()
    )
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found.")

    target = payload.target_status
    if target in NON_MANUAL_TARGET_STATES:
        raise HTTPException(
            status_code=409,
            detail=f"Order cannot be manually transitioned to {target}.",
        )

    allowed = VALID_ORDER_TRANSITIONS.get(order.order_status, set())
    if target not in allowed:
        raise HTTPException(
            status_code=409,
            detail=f"Invalid order transition from {order.order_status} to {target}.",
        )

    now = datetime.now(timezone.utc)
    prev = order.order_status

    if prev == "DRAFT" and target == "PENDING_PAYMENT":
        items = list(
            db.scalars(
                select(OrderItem).where(
                    OrderItem.order_id == order.id,
                    OrderItem.organisation_id == org_id,
                )
            ).all()
        )
        expires_at = now + timedelta(minutes=15)
        inventory_service.reserve_stock_for_order(
            db,
            organisation_id=org_id,
            order_id=order.id,
            order_item_allocations=[
                (i.id, i.product_id, i.location_id, i.quantity) for i in items
            ],
            expires_at=expires_at,
            actor_ref=org_ctx.user.email,
        )
        order.reservation_expires_at = expires_at

    elif target == "CANCELLED":
        inventory_service.release_order_reservations(
            db,
            organisation_id=org_id,
            order_id=order.id,
            target_status="RELEASED",
            actor_ref=org_ctx.user.email,
            reason=payload.reason or "Order cancelled",
        )
        if order.payment_status in ("UNPAID", "CREATED", "PENDING"):
            order.payment_status = "CANCELLED"

    order.order_status = target
    order.updated_at = now

    db.add(
        OrderEvent(
            organisation_id=org_id,
            order_id=order.id,
            from_status=prev,
            to_status=target,
            event_type="order_transitioned",
            actor_ref=org_ctx.user.email,
            details={"reason": payload.reason},
        )
    )
    db.add(
        AuditLog(
            organisation_id=org_id,
            actor_type=org_ctx.membership.role,
            actor_ref=org_ctx.user.email,
            action="commerce_order_transitioned",
            entity_name="orders",
            entity_id=str(order.id),
            details={
                "from_status": prev,
                "to_status": target,
                "reason": payload.reason,
                "status": "success",
            },
        )
    )
    db.commit()
    db.refresh(order)
    return _build_order_out(db, order, include_events=True)
