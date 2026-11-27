from datetime import datetime, timedelta, timezone
import uuid

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.auth_dependencies import OrgContext
from app.models.procurement import StockTransfer
from app.models.retail import (
    CommerceProduct,
    InventoryBalance,
    InventoryLocation,
    InventoryMovement,
    Order,
    OrderItem,
)
from app.models.rossmann import AuditLog
from app.schemas.expansion import (
    DamagedStockAdjustRequest,
    InventoryIntelligenceItemOut,
    InventoryIntelligenceOut,
    StockTransferCreate,
    StockTransferOut,
    WarehouseCreate,
    WarehouseOut,
)
from app.schemas.retail import format_minor_to_decimal_str
from app.services import inventory_service


def _generate_transfer_number(org_id: int) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    return f"TRF-{org_id}-{stamp}-{uuid.uuid4().hex[:6].upper()}"


def list_warehouses_with_stats(db: Session, org_id: int) -> list[WarehouseOut]:
    locations = list(
        db.scalars(
            select(InventoryLocation)
            .where(InventoryLocation.organisation_id == org_id)
            .order_by(InventoryLocation.is_default.desc(), InventoryLocation.id.asc())
        ).all()
    )
    stats_rows = db.execute(
        select(
            InventoryBalance.location_id,
            func.coalesce(func.sum(InventoryBalance.quantity), 0).label("total_units"),
            func.coalesce(func.sum(InventoryBalance.reserved_quantity), 0).label("reserved_units"),
            func.coalesce(func.sum(InventoryBalance.damaged_quantity), 0).label("damaged_units"),
        )
        .where(InventoryBalance.organisation_id == org_id)
        .group_by(InventoryBalance.location_id)
    ).all()
    stats = {int(r.location_id): r for r in stats_rows}

    result: list[WarehouseOut] = []
    for loc in locations:
        st = stats.get(loc.id)
        result.append(
            WarehouseOut(
                id=str(loc.id),
                organisation_id=loc.organisation_id,
                code=loc.code,
                name=loc.name,
                location_type=loc.location_type,
                address=loc.address,
                city=loc.city,
                state=loc.state,
                postal_code=loc.postal_code,
                is_default=loc.is_default,
                is_active=loc.is_active,
                total_units=int(st.total_units or 0) if st else 0,
                reserved_units=int(st.reserved_units or 0) if st else 0,
                damaged_units=int(st.damaged_units or 0) if st else 0,
                created_at=loc.created_at,
            )
        )
    return result


def create_warehouse(db: Session, org_ctx: OrgContext, payload: WarehouseCreate) -> WarehouseOut:
    org_id = org_ctx.organisation.id
    if payload.is_default:
        existing_defaults = db.scalars(
            select(InventoryLocation).where(
                InventoryLocation.organisation_id == org_id,
                InventoryLocation.is_default.is_(True),
            )
        ).all()
        for loc in existing_defaults:
            loc.is_default = False

    loc = InventoryLocation(
        organisation_id=org_id,
        code=payload.code.strip().upper(),
        name=payload.name.strip(),
        location_type=payload.location_type,
        address=payload.address,
        city=payload.city,
        state=payload.state,
        postal_code=payload.postal_code,
        is_default=payload.is_default,
        is_active=payload.is_active,
    )
    try:
        db.add(loc)
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="A warehouse or store with this code already exists in this organisation.",
        ) from exc

    db.add(
        AuditLog(
            organisation_id=org_id,
            actor_type=org_ctx.membership.role,
            actor_ref=org_ctx.user.email,
            action="warehouse_created",
            entity_name="inventory_locations",
            entity_id=str(loc.id),
            details={"code": loc.code, "name": loc.name, "location_type": loc.location_type},
        )
    )
    db.commit()
    db.refresh(loc)
    return WarehouseOut(
        id=str(loc.id),
        organisation_id=loc.organisation_id,
        code=loc.code,
        name=loc.name,
        location_type=loc.location_type,
        address=loc.address,
        city=loc.city,
        state=loc.state,
        postal_code=loc.postal_code,
        is_default=loc.is_default,
        is_active=loc.is_active,
        total_units=0,
        reserved_units=0,
        damaged_units=0,
        created_at=loc.created_at,
    )


def adjust_damaged_stock(
    db: Session, org_ctx: OrgContext, payload: DamagedStockAdjustRequest
) -> dict:
    if payload.quantity_delta == 0:
        raise HTTPException(status_code=422, detail="Damaged stock delta cannot be zero.")

    org_id = org_ctx.organisation.id
    product = db.scalar(
        select(CommerceProduct).where(
            CommerceProduct.id == payload.product_id,
            CommerceProduct.organisation_id == org_id,
        )
    )
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found.")
    location = db.scalar(
        select(InventoryLocation).where(
            InventoryLocation.id == payload.location_id,
            InventoryLocation.organisation_id == org_id,
        )
    )
    if location is None:
        raise HTTPException(status_code=404, detail="Location not found.")

    bal = inventory_service._get_or_create_balance_locked(db, org_id, product.id, location.id)
    new_damaged = bal.damaged_quantity + payload.quantity_delta
    if new_damaged < 0:
        raise HTTPException(status_code=409, detail="Damaged stock cannot become negative.")

    if payload.quantity_delta > 0:
        available = bal.quantity - bal.reserved_quantity
        if available < payload.quantity_delta:
            raise HTTPException(
                status_code=409,
                detail="Insufficient available physical stock to mark as damaged.",
            )
        bal.quantity -= payload.quantity_delta
        qty_delta = -payload.quantity_delta
    else:
        qty_delta = 0

    now = datetime.now(timezone.utc)
    bal.damaged_quantity = new_damaged
    bal.last_movement_at = now
    bal.updated_at = now

    db.add(
        InventoryMovement(
            organisation_id=org_id,
            balance_id=bal.id,
            product_id=product.id,
            location_id=location.id,
            movement_type="damaged",
            quantity_delta=qty_delta,
            reserved_delta=0,
            balance_after=bal.quantity,
            reserved_after=bal.reserved_quantity,
            reference_type="damaged_adjustment",
            reference_id=str(bal.id),
            reason=f"{payload.reason} (damaged_delta={payload.quantity_delta})",
            actor_ref=org_ctx.user.email,
        )
    )
    db.add(
        AuditLog(
            organisation_id=org_id,
            actor_type=org_ctx.membership.role,
            actor_ref=org_ctx.user.email,
            action="damaged_stock_adjusted",
            entity_name="inventory_balances",
            entity_id=str(bal.id),
            details={
                "product_id": product.id,
                "location_id": location.id,
                "damaged_after": bal.damaged_quantity,
                "available_after": bal.quantity - bal.reserved_quantity,
            },
        )
    )
    db.commit()
    return {
        "balance_id": str(bal.id),
        "on_hand": bal.quantity,
        "reserved": bal.reserved_quantity,
        "damaged": bal.damaged_quantity,
        "available": bal.quantity - bal.reserved_quantity,
    }


def _to_transfer_out(db: Session, tr: StockTransfer) -> StockTransferOut:
    product = db.get(CommerceProduct, tr.product_id)
    from_loc = db.get(InventoryLocation, tr.from_location_id)
    to_loc = db.get(InventoryLocation, tr.to_location_id)
    return StockTransferOut(
        id=str(tr.id),
        transfer_number=tr.transfer_number,
        organisation_id=tr.organisation_id,
        product_id=str(tr.product_id),
        product_name=product.name if product else f"Product #{tr.product_id}",
        sku=product.sku if product else "",
        from_location_id=tr.from_location_id,
        from_location_name=from_loc.name if from_loc else f"Location #{tr.from_location_id}",
        to_location_id=tr.to_location_id,
        to_location_name=to_loc.name if to_loc else f"Location #{tr.to_location_id}",
        quantity=tr.quantity,
        status=tr.status,
        requires_approval=tr.requires_approval,
        notes=tr.notes,
        requested_by=tr.requested_by,
        approved_by=tr.approved_by,
        dispatched_at=tr.dispatched_at,
        received_at=tr.received_at,
        created_at=tr.created_at,
    )


def create_stock_transfer(
    db: Session, org_ctx: OrgContext, payload: StockTransferCreate
) -> StockTransferOut:
    org_id = org_ctx.organisation.id
    if payload.from_location_id == payload.to_location_id:
        raise HTTPException(
            status_code=422, detail="Source and destination locations must be different."
        )

    product = db.scalar(
        select(CommerceProduct).where(
            CommerceProduct.id == payload.product_id,
            CommerceProduct.organisation_id == org_id,
        )
    )
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found.")

    from_loc = db.scalar(
        select(InventoryLocation).where(
            InventoryLocation.id == payload.from_location_id,
            InventoryLocation.organisation_id == org_id,
        )
    )
    to_loc = db.scalar(
        select(InventoryLocation).where(
            InventoryLocation.id == payload.to_location_id,
            InventoryLocation.organisation_id == org_id,
        )
    )
    if from_loc is None or to_loc is None:
        raise HTTPException(status_code=404, detail="Source or destination location not found.")

    initial_status = "PENDING_APPROVAL" if payload.requires_approval else "APPROVED"
    tr = StockTransfer(
        organisation_id=org_id,
        transfer_number=_generate_transfer_number(org_id),
        product_id=product.id,
        from_location_id=from_loc.id,
        to_location_id=to_loc.id,
        quantity=payload.quantity,
        status=initial_status,
        requires_approval=payload.requires_approval,
        notes=payload.notes,
        requested_by=org_ctx.user.email,
        approved_by=None if payload.requires_approval else org_ctx.user.email,
    )
    db.add(tr)
    db.flush()
    db.add(
        AuditLog(
            organisation_id=org_id,
            actor_type=org_ctx.membership.role,
            actor_ref=org_ctx.user.email,
            action="stock_transfer_created",
            entity_name="stock_transfers",
            entity_id=str(tr.id),
            details={"transfer_number": tr.transfer_number, "quantity": tr.quantity, "status": initial_status},
        )
    )
    db.commit()
    db.refresh(tr)
    return _to_transfer_out(db, tr)


def list_stock_transfers(
    db: Session, org_id: int, status: str | None = None
) -> list[StockTransferOut]:
    stmt = select(StockTransfer).where(StockTransfer.organisation_id == org_id)
    if status:
        stmt = stmt.where(StockTransfer.status == status.upper())
    rows = db.scalars(stmt.order_by(StockTransfer.id.desc())).all()
    return [_to_transfer_out(db, r) for r in rows]


def approve_stock_transfer(
    db: Session, org_ctx: OrgContext, transfer_id: int
) -> StockTransferOut:
    org_id = org_ctx.organisation.id
    tr = db.scalar(
        select(StockTransfer)
        .where(StockTransfer.id == transfer_id, StockTransfer.organisation_id == org_id)
        .with_for_update()
    )
    if tr is None:
        raise HTTPException(status_code=404, detail="Stock transfer not found.")
    if tr.status not in ("DRAFT", "PENDING_APPROVAL"):
        raise HTTPException(status_code=409, detail=f"Transfer in {tr.status} cannot be approved.")

    tr.status = "APPROVED"
    tr.approved_by = org_ctx.user.email
    tr.updated_at = datetime.now(timezone.utc)
    db.add(
        AuditLog(
            organisation_id=org_id,
            actor_type=org_ctx.membership.role,
            actor_ref=org_ctx.user.email,
            action="stock_transfer_approved",
            entity_name="stock_transfers",
            entity_id=str(tr.id),
            details={"transfer_number": tr.transfer_number},
        )
    )
    db.commit()
    db.refresh(tr)
    return _to_transfer_out(db, tr)


def dispatch_stock_transfer(
    db: Session, org_ctx: OrgContext, transfer_id: int
) -> StockTransferOut:
    org_id = org_ctx.organisation.id
    tr = db.scalar(
        select(StockTransfer)
        .where(StockTransfer.id == transfer_id, StockTransfer.organisation_id == org_id)
        .with_for_update()
    )
    if tr is None:
        raise HTTPException(status_code=404, detail="Stock transfer not found.")
    if tr.status != "APPROVED":
        raise HTTPException(status_code=409, detail="Transfer must be APPROVED before dispatch.")

    src = inventory_service._get_or_create_balance_locked(
        db, org_id, tr.product_id, tr.from_location_id
    )
    available = src.quantity - src.reserved_quantity
    if available < tr.quantity:
        raise HTTPException(
            status_code=409,
            detail=f"Insufficient available stock at source location ({available} available, {tr.quantity} requested).",
        )

    now = datetime.now(timezone.utc)
    src.quantity -= tr.quantity
    src.last_movement_at = now
    src.updated_at = now
    tr.status = "IN_TRANSIT"
    tr.dispatched_at = now
    tr.updated_at = now

    db.add(
        InventoryMovement(
            organisation_id=org_id,
            balance_id=src.id,
            product_id=tr.product_id,
            location_id=tr.from_location_id,
            movement_type="transfer_out",
            quantity_delta=-tr.quantity,
            reserved_delta=0,
            balance_after=src.quantity,
            reserved_after=src.reserved_quantity,
            reference_type="stock_transfer",
            reference_id=tr.transfer_number,
            reason=f"Dispatched transfer {tr.transfer_number} to location {tr.to_location_id}",
            actor_ref=org_ctx.user.email,
        )
    )
    db.add(
        AuditLog(
            organisation_id=org_id,
            actor_type=org_ctx.membership.role,
            actor_ref=org_ctx.user.email,
            action="stock_transfer_dispatched",
            entity_name="stock_transfers",
            entity_id=str(tr.id),
            details={"transfer_number": tr.transfer_number, "quantity": tr.quantity},
        )
    )
    db.commit()
    db.refresh(tr)
    return _to_transfer_out(db, tr)


def receive_stock_transfer(
    db: Session, org_ctx: OrgContext, transfer_id: int
) -> StockTransferOut:
    org_id = org_ctx.organisation.id
    tr = db.scalar(
        select(StockTransfer)
        .where(StockTransfer.id == transfer_id, StockTransfer.organisation_id == org_id)
        .with_for_update()
    )
    if tr is None:
        raise HTTPException(status_code=404, detail="Stock transfer not found.")
    if tr.status != "IN_TRANSIT":
        raise HTTPException(status_code=409, detail="Transfer must be IN_TRANSIT before receipt confirmation.")

    dest = inventory_service._get_or_create_balance_locked(
        db, org_id, tr.product_id, tr.to_location_id
    )
    now = datetime.now(timezone.utc)
    dest.quantity += tr.quantity
    dest.last_movement_at = now
    dest.updated_at = now
    tr.status = "RECEIVED"
    tr.received_at = now
    tr.updated_at = now

    db.add(
        InventoryMovement(
            organisation_id=org_id,
            balance_id=dest.id,
            product_id=tr.product_id,
            location_id=tr.to_location_id,
            movement_type="transfer_in",
            quantity_delta=tr.quantity,
            reserved_delta=0,
            balance_after=dest.quantity,
            reserved_after=dest.reserved_quantity,
            reference_type="stock_transfer",
            reference_id=tr.transfer_number,
            reason=f"Received transfer {tr.transfer_number} from location {tr.from_location_id}",
            actor_ref=org_ctx.user.email,
        )
    )
    db.add(
        AuditLog(
            organisation_id=org_id,
            actor_type=org_ctx.membership.role,
            actor_ref=org_ctx.user.email,
            action="stock_transfer_received",
            entity_name="stock_transfers",
            entity_id=str(tr.id),
            details={"transfer_number": tr.transfer_number, "quantity": tr.quantity},
        )
    )
    db.commit()
    db.refresh(tr)
    return _to_transfer_out(db, tr)


def get_inventory_intelligence(db: Session, org_id: int) -> InventoryIntelligenceOut:
    products = list(
        db.scalars(
            select(CommerceProduct)
            .where(CommerceProduct.organisation_id == org_id)
            .order_by(CommerceProduct.id.asc())
        ).all()
    )
    bal_rows = db.execute(
        select(
            InventoryBalance.product_id,
            func.coalesce(func.sum(InventoryBalance.quantity), 0).label("on_hand"),
            func.coalesce(func.sum(InventoryBalance.reserved_quantity), 0).label("reserved"),
            func.coalesce(func.sum(InventoryBalance.damaged_quantity), 0).label("damaged"),
            func.min(InventoryBalance.low_stock_threshold).label("threshold"),
            func.max(InventoryBalance.last_movement_at).label("last_movement_at"),
        )
        .where(InventoryBalance.organisation_id == org_id)
        .group_by(InventoryBalance.product_id)
    ).all()
    bal_map = {int(r.product_id): r for r in bal_rows}

    since_30d = datetime.now(timezone.utc) - timedelta(days=30)
    sold_rows = db.execute(
        select(
            OrderItem.product_id,
            func.coalesce(func.sum(OrderItem.quantity), 0).label("units_sold"),
        )
        .join(Order, Order.id == OrderItem.order_id)
        .where(
            OrderItem.organisation_id == org_id,
            Order.order_status.in_(("PAID", "PROCESSING", "FULFILLED")),
            Order.placed_at >= since_30d,
        )
        .group_by(OrderItem.product_id)
    ).all()
    sold_map = {int(r.product_id): int(r.units_sold or 0) for r in sold_rows}

    now = datetime.now(timezone.utc)
    items: list[InventoryIntelligenceItemOut] = []
    total_val_minor = 0
    low_count = 0
    oos_count = 0
    dead_count = 0
    any_sales = sum(sold_map.values()) > 0

    for prod in products:
        b = bal_map.get(prod.id)
        on_hand = int(b.on_hand or 0) if b else 0
        reserved = int(b.reserved or 0) if b else 0
        damaged = int(b.damaged or 0) if b else 0
        available = max(0, on_hand - reserved)
        threshold = (
            int(b.threshold)
            if (b and b.threshold is not None)
            else prod.reorder_threshold
        )
        units_30d = sold_map.get(prod.id, 0)
        last_mv = b.last_movement_at if b else None
        days_since = (now - last_mv).days if last_mv is not None else None
        unit_val = prod.cost_price_minor if prod.cost_price_minor is not None else prod.price_minor
        stock_val = on_hand * unit_val
        total_val_minor += stock_val

        if available <= 0:
            oos_count += 1
        elif available <= threshold:
            low_count += 1

        if on_hand > 0 and units_30d == 0 and (days_since is None or days_since >= 30):
            classification = "dead_stock" if days_since is not None and days_since >= 60 else "slow_moving"
            if classification == "dead_stock":
                dead_count += 1
        elif units_30d >= 10:
            classification = "fast_moving"
        elif units_30d > 0:
            classification = "steady"
        else:
            classification = "insufficient_data" if not any_sales else "slow_moving"

        target_cover = max(threshold * 2, units_30d)
        suggested_reorder = max(0, target_cover - available) if available <= threshold else 0

        items.append(
            InventoryIntelligenceItemOut(
                product_id=str(prod.id),
                sku=prod.sku,
                product_name=prod.name,
                on_hand=on_hand,
                reserved=reserved,
                available=available,
                damaged=damaged,
                reorder_threshold=threshold,
                units_sold_30d=units_30d,
                suggested_reorder_qty=suggested_reorder,
                classification=classification,
                days_since_movement=days_since,
                stock_value_minor=stock_val,
                stock_value=format_minor_to_decimal_str(stock_val),
            )
        )

    return InventoryIntelligenceOut(
        total_stock_value_minor=total_val_minor,
        total_stock_value=format_minor_to_decimal_str(total_val_minor),
        low_stock_count=low_count,
        out_of_stock_count=oos_count,
        dead_stock_count=dead_count,
        insufficient_data=not any_sales,
        note=(
            "Insufficient recent order history for turnover classification; showing threshold-based alerts."
            if not any_sales
            else None
        ),
        items=items,
    )
