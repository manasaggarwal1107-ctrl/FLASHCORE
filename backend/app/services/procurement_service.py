from datetime import datetime, timezone
import uuid

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.auth_dependencies import OrgContext
from app.models.procurement import PurchaseOrder, PurchaseOrderItem, Supplier
from app.models.retail import CommerceProduct, InventoryLocation, InventoryMovement
from app.models.rossmann import AuditLog
from app.schemas.expansion import (
    PurchaseOrderCreate,
    PurchaseOrderItemOut,
    PurchaseOrderOut,
    PurchaseOrderReceiveRequest,
    SupplierCreate,
    SupplierOut,
)
from app.schemas.retail import format_minor_to_decimal_str
from app.services import inventory_service


def _generate_po_number(org_id: int) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    return f"PO-{org_id}-{stamp}-{uuid.uuid4().hex[:6].upper()}"


def create_supplier(db: Session, org_ctx: OrgContext, payload: SupplierCreate) -> SupplierOut:
    org_id = org_ctx.organisation.id
    sup = Supplier(
        organisation_id=org_id,
        code=payload.code.strip().upper(),
        name=payload.name.strip(),
        contact_name=payload.contact_name,
        email=payload.email,
        phone=payload.phone,
        gstin=payload.gstin.strip().upper() if payload.gstin else None,
        state_code=payload.state_code.strip() if payload.state_code else None,
        address=payload.address,
        payment_terms=payload.payment_terms,
        status=payload.status,
    )
    try:
        db.add(sup)
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Supplier code already exists in this organisation.") from exc

    db.add(
        AuditLog(
            organisation_id=org_id,
            actor_type=org_ctx.membership.role,
            actor_ref=org_ctx.user.email,
            action="supplier_created",
            entity_name="suppliers",
            entity_id=str(sup.id),
            details={"code": sup.code, "name": sup.name},
        )
    )
    db.commit()
    db.refresh(sup)
    return SupplierOut(
        id=str(sup.id),
        organisation_id=sup.organisation_id,
        code=sup.code,
        name=sup.name,
        contact_name=sup.contact_name,
        email=sup.email,
        phone=sup.phone,
        gstin=sup.gstin,
        state_code=sup.state_code,
        outstanding_payable_minor=sup.outstanding_payable_minor,
        outstanding_payable=format_minor_to_decimal_str(sup.outstanding_payable_minor),
        address=sup.address,
        payment_terms=sup.payment_terms,
        status=sup.status,
        order_count=0,
        total_spend_minor=0,
        total_spend="0.00",
        created_at=sup.created_at,
    )


def list_suppliers(db: Session, org_id: int) -> list[SupplierOut]:
    suppliers = list(
        db.scalars(
            select(Supplier)
            .where(Supplier.organisation_id == org_id)
            .order_by(Supplier.id.desc())
        ).all()
    )
    po_stats = db.execute(
        select(
            PurchaseOrder.supplier_id,
            func.count(PurchaseOrder.id).label("order_count"),
            func.coalesce(func.sum(PurchaseOrder.total_cost_minor), 0).label("total_spend"),
        )
        .where(
            PurchaseOrder.organisation_id == org_id,
            PurchaseOrder.status != "CANCELLED",
        )
        .group_by(PurchaseOrder.supplier_id)
    ).all()
    stats = {int(r.supplier_id): r for r in po_stats}

    out: list[SupplierOut] = []
    for s in suppliers:
        st = stats.get(s.id)
        spend = int(st.total_spend or 0) if st else 0
        out.append(
            SupplierOut(
                id=str(s.id),
                organisation_id=s.organisation_id,
                code=s.code,
                name=s.name,
                contact_name=s.contact_name,
                email=s.email,
                phone=s.phone,
                gstin=s.gstin,
                state_code=s.state_code,
                outstanding_payable_minor=s.outstanding_payable_minor,
                outstanding_payable=format_minor_to_decimal_str(s.outstanding_payable_minor),
                address=s.address,
                payment_terms=s.payment_terms,
                status=s.status,
                order_count=int(st.order_count or 0) if st else 0,
                total_spend_minor=spend,
                total_spend=format_minor_to_decimal_str(spend),
                created_at=s.created_at,
            )
        )
    return out


def _to_po_out(db: Session, po: PurchaseOrder) -> PurchaseOrderOut:
    supplier = db.get(Supplier, po.supplier_id)
    location = db.get(InventoryLocation, po.location_id)
    items = list(
        db.scalars(
            select(PurchaseOrderItem)
            .where(
                PurchaseOrderItem.purchase_order_id == po.id,
                PurchaseOrderItem.organisation_id == po.organisation_id,
            )
            .order_by(PurchaseOrderItem.id.asc())
        ).all()
    )
    prod_ids = [i.product_id for i in items]
    products = (
        {
            p.id: p
            for p in db.scalars(
                select(CommerceProduct).where(CommerceProduct.id.in_(prod_ids))
            ).all()
        }
        if prod_ids
        else {}
    )
    item_outs = [
        PurchaseOrderItemOut(
            id=str(it.id),
            product_id=str(it.product_id),
            sku=products[it.product_id].sku if it.product_id in products else "",
            product_name=products[it.product_id].name if it.product_id in products else f"Product #{it.product_id}",
            ordered_quantity=it.ordered_quantity,
            received_quantity=it.received_quantity,
            unit_cost_minor=it.unit_cost_minor,
            unit_cost=format_minor_to_decimal_str(it.unit_cost_minor),
            line_total_minor=it.line_total_minor,
            line_total=format_minor_to_decimal_str(it.line_total_minor),
        )
        for it in items
    ]
    return PurchaseOrderOut(
        id=str(po.id),
        organisation_id=po.organisation_id,
        po_number=po.po_number,
        supplier_id=str(po.supplier_id),
        supplier_name=supplier.name if supplier else f"Supplier #{po.supplier_id}",
        location_id=po.location_id,
        location_name=location.name if location else f"Location #{po.location_id}",
        status=po.status,
        currency=po.currency,
        total_cost_minor=po.total_cost_minor,
        total_cost=format_minor_to_decimal_str(po.total_cost_minor),
        expected_at=po.expected_at,
        submitted_at=po.submitted_at,
        received_at=po.received_at,
        notes=po.notes,
        created_by=po.created_by,
        items=item_outs,
        created_at=po.created_at,
    )


def create_purchase_order(
    db: Session, org_ctx: OrgContext, payload: PurchaseOrderCreate
) -> PurchaseOrderOut:
    org_id = org_ctx.organisation.id
    supplier = db.scalar(
        select(Supplier).where(
            Supplier.id == payload.supplier_id,
            Supplier.organisation_id == org_id,
        )
    )
    if supplier is None:
        raise HTTPException(status_code=404, detail="Supplier not found.")
    location = db.scalar(
        select(InventoryLocation).where(
            InventoryLocation.id == payload.location_id,
            InventoryLocation.organisation_id == org_id,
        )
    )
    if location is None:
        raise HTTPException(status_code=404, detail="Destination warehouse/location not found.")

    total_cost = 0
    prepared_items: list[tuple[CommerceProduct, int, int, int]] = []
    for item in payload.items:
        prod = db.scalar(
            select(CommerceProduct).where(
                CommerceProduct.id == item.product_id,
                CommerceProduct.organisation_id == org_id,
            )
        )
        if prod is None:
            raise HTTPException(status_code=404, detail=f"Product {item.product_id} not found.")
        line_total = item.ordered_quantity * item.unit_cost_minor
        total_cost += line_total
        prepared_items.append((prod, item.ordered_quantity, item.unit_cost_minor, line_total))

    po = PurchaseOrder(
        organisation_id=org_id,
        po_number=_generate_po_number(org_id),
        supplier_id=supplier.id,
        location_id=location.id,
        status="DRAFT",
        currency="INR",
        total_cost_minor=total_cost,
        expected_at=payload.expected_at,
        notes=payload.notes,
        created_by=org_ctx.user.email,
    )
    db.add(po)
    db.flush()

    for prod, qty, unit_cost, line_total in prepared_items:
        db.add(
            PurchaseOrderItem(
                organisation_id=org_id,
                purchase_order_id=po.id,
                product_id=prod.id,
                ordered_quantity=qty,
                received_quantity=0,
                unit_cost_minor=unit_cost,
                line_total_minor=line_total,
            )
        )

    db.add(
        AuditLog(
            organisation_id=org_id,
            actor_type=org_ctx.membership.role,
            actor_ref=org_ctx.user.email,
            action="purchase_order_created",
            entity_name="purchase_orders",
            entity_id=str(po.id),
            details={"po_number": po.po_number, "supplier_id": supplier.id, "total_cost_minor": total_cost},
        )
    )
    db.commit()
    db.refresh(po)
    return _to_po_out(db, po)


def list_purchase_orders(
    db: Session, org_id: int, status: str | None = None
) -> list[PurchaseOrderOut]:
    stmt = select(PurchaseOrder).where(PurchaseOrder.organisation_id == org_id)
    if status:
        stmt = stmt.where(PurchaseOrder.status == status.upper())
    rows = db.scalars(stmt.order_by(PurchaseOrder.id.desc())).all()
    return [_to_po_out(db, r) for r in rows]


def submit_purchase_order(db: Session, org_ctx: OrgContext, po_id: int) -> PurchaseOrderOut:
    org_id = org_ctx.organisation.id
    po = db.scalar(
        select(PurchaseOrder)
        .where(PurchaseOrder.id == po_id, PurchaseOrder.organisation_id == org_id)
        .with_for_update()
    )
    if po is None:
        raise HTTPException(status_code=404, detail="Purchase order not found.")
    if po.status != "DRAFT":
        raise HTTPException(status_code=409, detail=f"PO in status {po.status} cannot be submitted.")

    now = datetime.now(timezone.utc)
    po.status = "SUBMITTED"
    po.submitted_at = now
    po.updated_at = now
    db.add(
        AuditLog(
            organisation_id=org_id,
            actor_type=org_ctx.membership.role,
            actor_ref=org_ctx.user.email,
            action="purchase_order_submitted",
            entity_name="purchase_orders",
            entity_id=str(po.id),
            details={"po_number": po.po_number},
        )
    )
    db.commit()
    db.refresh(po)
    return _to_po_out(db, po)


def receive_purchase_order(
    db: Session,
    org_ctx: OrgContext,
    po_id: int,
    payload: PurchaseOrderReceiveRequest,
) -> PurchaseOrderOut:
    org_id = org_ctx.organisation.id
    po = db.scalar(
        select(PurchaseOrder)
        .where(PurchaseOrder.id == po_id, PurchaseOrder.organisation_id == org_id)
        .with_for_update()
    )
    if po is None:
        raise HTTPException(status_code=404, detail="Purchase order not found.")
    if po.status not in ("SUBMITTED", "PARTIALLY_RECEIVED"):
        raise HTTPException(
            status_code=409,
            detail=f"PO in status {po.status} cannot receive goods.",
        )

    po_items = {
        it.id: it
        for it in db.scalars(
            select(PurchaseOrderItem)
            .where(
                PurchaseOrderItem.purchase_order_id == po.id,
                PurchaseOrderItem.organisation_id == org_id,
            )
            .with_for_update()
        ).all()
    }

    now = datetime.now(timezone.utc)
    for rec in payload.items:
        it = po_items.get(rec.item_id)
        if it is None:
            raise HTTPException(status_code=404, detail=f"PO item {rec.item_id} not found.")
        remaining = it.ordered_quantity - it.received_quantity
        if rec.quantity_received > remaining:
            raise HTTPException(
                status_code=409,
                detail=f"Cannot receive {rec.quantity_received} units; only {remaining} remaining for item {it.id}.",
            )
        bal = inventory_service._get_or_create_balance_locked(
            db, org_id, it.product_id, po.location_id
        )
        it.received_quantity += rec.quantity_received
        bal.quantity += rec.quantity_received
        bal.last_movement_at = now
        bal.updated_at = now

        db.add(
            InventoryMovement(
                organisation_id=org_id,
                balance_id=bal.id,
                product_id=it.product_id,
                location_id=po.location_id,
                movement_type="receipt",
                quantity_delta=rec.quantity_received,
                reserved_delta=0,
                balance_after=bal.quantity,
                reserved_after=bal.reserved_quantity,
                reference_type="purchase_order",
                reference_id=po.po_number,
                reason=payload.note or f"Goods receipt for PO {po.po_number}",
                actor_ref=org_ctx.user.email,
            )
        )

    all_done = all(it.received_quantity >= it.ordered_quantity for it in po_items.values())
    po.status = "COMPLETED" if all_done else "PARTIALLY_RECEIVED"
    if all_done:
        po.received_at = now
    po.updated_at = now

    db.add(
        AuditLog(
            organisation_id=org_id,
            actor_type=org_ctx.membership.role,
            actor_ref=org_ctx.user.email,
            action="purchase_order_goods_received",
            entity_name="purchase_orders",
            entity_id=str(po.id),
            details={"po_number": po.po_number, "status": po.status},
        )
    )
    db.commit()
    db.refresh(po)
    return _to_po_out(db, po)
