from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.auth_dependencies import OrgContext
from app.models.retail import (
    CommerceProduct,
    InventoryBalance,
    InventoryLocation,
    InventoryMovement,
    InventoryReservation,
    Order,
    OrderEvent,
)
from app.models.rossmann import AuditLog
from app.schemas.retail import (
    InventoryAdjustmentCreate,
    InventoryBalanceOut,
    InventoryLocationCreate,
    InventoryMovementOut,
)


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def get_or_create_default_location(
    db: Session, organisation_id: int
) -> InventoryLocation:
    existing = db.scalar(
        select(InventoryLocation)
        .where(
            InventoryLocation.organisation_id == organisation_id,
            InventoryLocation.is_active.is_(True),
        )
        .order_by(InventoryLocation.id.asc())
    )
    if existing is not None:
        return existing

    loc = InventoryLocation(
        organisation_id=organisation_id,
        code="MAIN-WH",
        name="Main Warehouse",
        location_type="warehouse",
        is_active=True,
    )
    try:
        with db.begin_nested():
            db.add(loc)
            db.flush()
        return loc
    except IntegrityError:
        existing = db.scalar(
            select(InventoryLocation).where(
                InventoryLocation.organisation_id == organisation_id,
                InventoryLocation.code == "MAIN-WH",
            )
        )
        if existing is None:
            raise
        return existing


def create_location(
    db: Session, org_ctx: OrgContext, payload: InventoryLocationCreate
) -> InventoryLocation:
    org_id = org_ctx.organisation.id
    loc = InventoryLocation(
        organisation_id=org_id,
        code=payload.code,
        name=payload.name,
        location_type=payload.location_type,
        is_active=payload.is_active,
    )
    try:
        db.add(loc)
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="An inventory location with this code already exists in this organisation.",
        ) from exc

    db.add(
        AuditLog(
            organisation_id=org_id,
            actor_type=org_ctx.membership.role,
            actor_ref=org_ctx.user.email,
            action="inventory_location_created",
            entity_name="inventory_locations",
            entity_id=str(loc.id),
            details={"code": loc.code, "name": loc.name, "status": "success"},
        )
    )
    db.commit()
    db.refresh(loc)
    return loc


def list_locations(db: Session, org_id: int) -> list[InventoryLocation]:
    return list(
        db.scalars(
            select(InventoryLocation)
            .where(InventoryLocation.organisation_id == org_id)
            .order_by(InventoryLocation.id.asc())
        ).all()
    )


def _get_or_create_balance_locked(
    db: Session,
    organisation_id: int,
    product_id: int,
    location_id: int,
) -> InventoryBalance:
    bal = db.scalar(
        select(InventoryBalance)
        .where(
            InventoryBalance.organisation_id == organisation_id,
            InventoryBalance.product_id == product_id,
            InventoryBalance.location_id == location_id,
        )
        .with_for_update()
    )
    if bal is not None:
        return bal

    bal = InventoryBalance(
        organisation_id=organisation_id,
        product_id=product_id,
        location_id=location_id,
        quantity=0,
        reserved_quantity=0,
        low_stock_threshold=5,
    )
    try:
        with db.begin_nested():
            db.add(bal)
            db.flush()
    except IntegrityError:
        pass

    bal = db.scalar(
        select(InventoryBalance)
        .where(
            InventoryBalance.organisation_id == organisation_id,
            InventoryBalance.product_id == product_id,
            InventoryBalance.location_id == location_id,
        )
        .with_for_update()
    )
    if bal is None:
        raise HTTPException(status_code=409, detail="Failed to lock inventory balance.")
    return bal


def adjust_stock(
    db: Session, org_ctx: OrgContext, payload: InventoryAdjustmentCreate
) -> InventoryBalanceOut:
    if payload.quantity_delta == 0:
        raise HTTPException(
            status_code=422, detail="Quantity adjustment cannot be zero."
        )

    org_id = org_ctx.organisation.id
    product = db.scalar(
        select(CommerceProduct).where(
            CommerceProduct.id == payload.product_id,
            CommerceProduct.organisation_id == org_id,
        )
    )
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found.")

    if payload.location_id is not None:
        location = db.scalar(
            select(InventoryLocation).where(
                InventoryLocation.id == payload.location_id,
                InventoryLocation.organisation_id == org_id,
            )
        )
        if location is None:
            raise HTTPException(status_code=404, detail="Inventory location not found.")
    else:
        location = get_or_create_default_location(db, org_id)

    balance = _get_or_create_balance_locked(db, org_id, product.id, location.id)
    old_qty = balance.quantity
    new_qty = old_qty + payload.quantity_delta

    if new_qty < 0 or new_qty < balance.reserved_quantity:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "Adjustment would reduce physical stock below reserved stock.",
                "current_quantity": old_qty,
                "reserved_quantity": balance.reserved_quantity,
                "requested_quantity": new_qty,
            },
        )

    balance.quantity = new_qty
    if payload.low_stock_threshold is not None:
        balance.low_stock_threshold = payload.low_stock_threshold
    balance.updated_at = datetime.now(timezone.utc)

    db.add(
        InventoryMovement(
            organisation_id=org_id,
            balance_id=balance.id,
            product_id=product.id,
            location_id=location.id,
            movement_type="adjustment",
            quantity_delta=payload.quantity_delta,
            reserved_delta=0,
            balance_after=new_qty,
            reserved_after=balance.reserved_quantity,
            reference_type="manual_adjustment",
            reference_id=str(balance.id),
            reason=payload.reason,
            actor_ref=org_ctx.user.email,
        )
    )
    db.add(
        AuditLog(
            organisation_id=org_id,
            actor_type=org_ctx.membership.role,
            actor_ref=org_ctx.user.email,
            action="commerce_inventory_adjusted",
            entity_name="inventory_balances",
            entity_id=str(balance.id),
            details={
                "product_id": product.id,
                "location_id": location.id,
                "quantity_before": old_qty,
                "quantity_delta": payload.quantity_delta,
                "quantity_after": new_qty,
                "reason": payload.reason,
                "status": "success",
            },
        )
    )
    db.commit()
    db.refresh(balance)

    return InventoryBalanceOut(
        id=balance.id,
        product_id=str(product.id),
        sku=product.sku,
        product_name=product.name,
        location_id=location.id,
        location_code=location.code,
        location_name=location.name,
        on_hand=balance.quantity,
        reserved=balance.reserved_quantity,
        available=balance.quantity - balance.reserved_quantity,
        low_stock_threshold=balance.low_stock_threshold,
        origin="real",
        updated_at=balance.updated_at,
    )


def list_balances(
    db: Session,
    org_id: int,
    *,
    page: int = 1,
    page_size: int = 25,
    search: str | None = None,
    location_id: int | None = None,
) -> dict:
    base = (
        select(InventoryBalance, CommerceProduct, InventoryLocation)
        .join(CommerceProduct, CommerceProduct.id == InventoryBalance.product_id)
        .join(InventoryLocation, InventoryLocation.id == InventoryBalance.location_id)
        .where(
            InventoryBalance.organisation_id == org_id,
            CommerceProduct.organisation_id == org_id,
            InventoryLocation.organisation_id == org_id,
        )
    )
    count_q = (
        select(func.count(InventoryBalance.id))
        .join(CommerceProduct, CommerceProduct.id == InventoryBalance.product_id)
        .where(
            InventoryBalance.organisation_id == org_id,
            CommerceProduct.organisation_id == org_id,
        )
    )

    if location_id is not None:
        base = base.where(InventoryBalance.location_id == location_id)
        count_q = count_q.where(InventoryBalance.location_id == location_id)

    if search:
        pattern = f"%{_escape_like(search.strip())}%"
        filt = CommerceProduct.name.ilike(pattern, escape="\\") | CommerceProduct.sku.ilike(
            pattern, escape="\\"
        )
        base = base.where(filt)
        count_q = count_q.where(filt)

    total = db.scalar(count_q) or 0
    offset = (page - 1) * page_size
    rows = db.execute(
        base.order_by(InventoryBalance.id.desc()).offset(offset).limit(page_size)
    ).all()

    items = [
        InventoryBalanceOut(
            id=bal.id,
            product_id=str(prod.id),
            sku=prod.sku,
            product_name=prod.name,
            location_id=loc.id,
            location_code=loc.code,
            location_name=loc.name,
            on_hand=bal.quantity,
            reserved=bal.reserved_quantity,
            available=bal.quantity - bal.reserved_quantity,
            low_stock_threshold=bal.low_stock_threshold,
            origin="real",
            updated_at=bal.updated_at,
        )
        for bal, prod, loc in rows
    ]
    return {"items": items, "total": total, "page": page, "page_size": page_size}


def list_movements(
    db: Session,
    org_id: int,
    *,
    page: int = 1,
    page_size: int = 25,
    search: str | None = None,
) -> dict:
    base = (
        select(InventoryMovement, CommerceProduct, InventoryLocation)
        .join(CommerceProduct, CommerceProduct.id == InventoryMovement.product_id)
        .join(InventoryLocation, InventoryLocation.id == InventoryMovement.location_id)
        .where(
            InventoryMovement.organisation_id == org_id,
            CommerceProduct.organisation_id == org_id,
            InventoryLocation.organisation_id == org_id,
        )
    )
    count_q = (
        select(func.count(InventoryMovement.id))
        .join(CommerceProduct, CommerceProduct.id == InventoryMovement.product_id)
        .where(
            InventoryMovement.organisation_id == org_id,
            CommerceProduct.organisation_id == org_id,
        )
    )

    if search:
        pattern = f"%{_escape_like(search.strip())}%"
        filt = (
            CommerceProduct.name.ilike(pattern, escape="\\")
            | CommerceProduct.sku.ilike(pattern, escape="\\")
            | InventoryMovement.reason.ilike(pattern, escape="\\")
        )
        base = base.where(filt)
        count_q = count_q.where(filt)

    total = db.scalar(count_q) or 0
    offset = (page - 1) * page_size
    rows = db.execute(
        base.order_by(InventoryMovement.id.desc()).offset(offset).limit(page_size)
    ).all()

    items = [
        InventoryMovementOut(
            id=str(mov.id),
            balance_id=mov.balance_id,
            product_id=str(prod.id),
            sku=prod.sku,
            product_name=prod.name,
            location_id=loc.id,
            location_name=loc.name,
            type=mov.movement_type,
            quantity_delta=mov.quantity_delta,
            reserved_delta=mov.reserved_delta,
            balance_after=mov.balance_after,
            reserved_after=mov.reserved_after,
            reference_type=mov.reference_type,
            reference_id=mov.reference_id,
            reason=mov.reason,
            actor=mov.actor_ref,
            origin="real",
            occurred_at=mov.created_at,
        )
        for mov, prod, loc in rows
    ]
    return {"items": items, "total": total, "page": page, "page_size": page_size}


def reserve_stock_for_order(
    db: Session,
    *,
    organisation_id: int,
    order_id: int,
    order_item_allocations: list[tuple[int, int, int, int]],
    expires_at: datetime,
    actor_ref: str | None,
) -> list[InventoryReservation]:
    """Reserve stock for `(order_item_id, product_id, location_id, qty)` tuples.

    Locks `inventory_balances` in deterministic `(product_id, location_id)` order
    to eliminate multi-line checkout deadlocks.
    """
    ordered = sorted(order_item_allocations, key=lambda x: (x[1], x[2], x[0]))
    created_reservations: list[InventoryReservation] = []

    for order_item_id, product_id, location_id, qty in ordered:
        balance = db.scalar(
            select(InventoryBalance)
            .where(
                InventoryBalance.organisation_id == organisation_id,
                InventoryBalance.product_id == product_id,
                InventoryBalance.location_id == location_id,
            )
            .with_for_update()
        )
        if balance is None:
            raise HTTPException(
                status_code=409,
                detail={
                    "message": "No inventory balance exists for the requested product and location.",
                    "product_id": product_id,
                    "location_id": location_id,
                },
            )

        available = balance.quantity - balance.reserved_quantity
        if available < qty:
            raise HTTPException(
                status_code=409,
                detail={
                    "message": "Insufficient available inventory to reserve.",
                    "product_id": product_id,
                    "location_id": location_id,
                    "available": available,
                    "requested": qty,
                },
            )

        balance.reserved_quantity += qty
        balance.updated_at = datetime.now(timezone.utc)

        res = InventoryReservation(
            organisation_id=organisation_id,
            order_id=order_id,
            order_item_id=order_item_id,
            balance_id=balance.id,
            quantity=qty,
            status="PENDING",
            expires_at=expires_at,
        )
        db.add(res)
        db.flush()
        created_reservations.append(res)

        db.add(
            InventoryMovement(
                organisation_id=organisation_id,
                balance_id=balance.id,
                product_id=product_id,
                location_id=location_id,
                movement_type="reservation",
                quantity_delta=0,
                reserved_delta=qty,
                balance_after=balance.quantity,
                reserved_after=balance.reserved_quantity,
                reference_type="order",
                reference_id=str(order_id),
                reason="Stock reserved for order checkout",
                actor_ref=actor_ref,
            )
        )

    return created_reservations


def confirm_order_reservations(
    db: Session,
    *,
    organisation_id: int,
    order_id: int,
    actor_ref: str | None,
) -> None:
    reservations = list(
        db.scalars(
            select(InventoryReservation)
            .where(
                InventoryReservation.organisation_id == organisation_id,
                InventoryReservation.order_id == order_id,
                InventoryReservation.status == "PENDING",
            )
            .order_by(InventoryReservation.balance_id.asc(), InventoryReservation.id.asc())
            .with_for_update()
        ).all()
    )
    if not reservations:
        return

    now = datetime.now(timezone.utc)
    for res in reservations:
        balance = db.scalar(
            select(InventoryBalance)
            .where(
                InventoryBalance.id == res.balance_id,
                InventoryBalance.organisation_id == organisation_id,
            )
            .with_for_update()
        )
        if balance is None:
            raise HTTPException(
                status_code=409, detail="Reserved inventory balance is missing."
            )
        if balance.quantity < res.quantity or balance.reserved_quantity < res.quantity:
            raise HTTPException(
                status_code=409, detail="Inventory balance invariant violated."
            )

        balance.quantity -= res.quantity
        balance.reserved_quantity -= res.quantity
        balance.updated_at = now
        res.status = "CONFIRMED"
        res.updated_at = now

        db.add(
            InventoryMovement(
                organisation_id=organisation_id,
                balance_id=balance.id,
                product_id=balance.product_id,
                location_id=balance.location_id,
                movement_type="sale",
                quantity_delta=-res.quantity,
                reserved_delta=-res.quantity,
                balance_after=balance.quantity,
                reserved_after=balance.reserved_quantity,
                reference_type="order",
                reference_id=str(order_id),
                reason="Order payment captured; reservation confirmed",
                actor_ref=actor_ref,
            )
        )


def release_order_reservations(
    db: Session,
    *,
    organisation_id: int,
    order_id: int,
    target_status: str = "RELEASED",
    actor_ref: str | None = None,
    reason: str = "Order cancelled; reservation released",
) -> int:
    if target_status not in ("RELEASED", "EXPIRED"):
        raise ValueError("Invalid release reservation target status")

    reservations = list(
        db.scalars(
            select(InventoryReservation)
            .where(
                InventoryReservation.organisation_id == organisation_id,
                InventoryReservation.order_id == order_id,
                InventoryReservation.status == "PENDING",
            )
            .order_by(InventoryReservation.balance_id.asc(), InventoryReservation.id.asc())
            .with_for_update()
        ).all()
    )
    if not reservations:
        return 0

    now = datetime.now(timezone.utc)
    mov_type = "expiry" if target_status == "EXPIRED" else "release"
    for res in reservations:
        balance = db.scalar(
            select(InventoryBalance)
            .where(
                InventoryBalance.id == res.balance_id,
                InventoryBalance.organisation_id == organisation_id,
            )
            .with_for_update()
        )
        if balance is None:
            raise HTTPException(
                status_code=409, detail="Reserved inventory balance is missing."
            )
        if balance.reserved_quantity < res.quantity:
            raise HTTPException(
                status_code=409, detail="Inventory reserved quantity invariant violated."
            )

        balance.reserved_quantity -= res.quantity
        balance.updated_at = now
        res.status = target_status
        res.updated_at = now

        db.add(
            InventoryMovement(
                organisation_id=organisation_id,
                balance_id=balance.id,
                product_id=balance.product_id,
                location_id=balance.location_id,
                movement_type=mov_type,
                quantity_delta=0,
                reserved_delta=-res.quantity,
                balance_after=balance.quantity,
                reserved_after=balance.reserved_quantity,
                reference_type="order",
                reference_id=str(order_id),
                reason=reason,
                actor_ref=actor_ref,
            )
        )
    return len(reservations)


def expire_stale_reservations(
    db: Session,
    *,
    organisation_id: int,
    actor_ref: str | None = "system:expiry-sweeper",
) -> int:
    now = datetime.now(timezone.utc)
    stale_order_ids = list(
        db.scalars(
            select(InventoryReservation.order_id)
            .where(
                InventoryReservation.organisation_id == organisation_id,
                InventoryReservation.status == "PENDING",
                InventoryReservation.expires_at <= now,
            )
            .distinct()
        ).all()
    )
    expired_orders = 0
    for oid in stale_order_ids:
        order = db.scalar(
            select(Order)
            .where(Order.id == oid, Order.organisation_id == organisation_id)
            .with_for_update()
        )
        if order is None:
            continue
        released = release_order_reservations(
            db,
            organisation_id=organisation_id,
            order_id=order.id,
            target_status="EXPIRED",
            actor_ref=actor_ref,
            reason="Reservation expired",
        )
        if released > 0 and order.order_status in ("DRAFT", "PENDING_PAYMENT"):
            prev = order.order_status
            order.order_status = "EXPIRED"
            if order.payment_status in ("UNPAID", "CREATED", "PENDING"):
                order.payment_status = "CANCELLED"
            order.updated_at = now
            db.add(
                OrderEvent(
                    organisation_id=organisation_id,
                    order_id=order.id,
                    from_status=prev,
                    to_status="EXPIRED",
                    event_type="reservation_expired",
                    actor_ref=actor_ref,
                    details={"released_reservations": released},
                )
            )
            expired_orders += 1

    if expired_orders > 0:
        db.commit()
    return expired_orders
