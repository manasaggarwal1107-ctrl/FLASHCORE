from datetime import datetime, timezone
import uuid

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.auth_dependencies import OrgContext
from app.models.finance import PaymentRefund
from app.models.operations import OrderReturn, OrderReturnItem
from app.models.payments import PaymentTransaction
from app.models.retail import (
    CommerceProduct,
    InventoryMovement,
    Order,
    OrderItem,
)
from app.models.rossmann import AuditLog
from app.schemas.expansion import (
    ReturnCreate,
    ReturnItemOut,
    ReturnOut,
    ReturnReviewRequest,
)
from app.schemas.finance import RefundCreateRequest
from app.schemas.retail import format_minor_to_decimal_str
from app.services import inventory_service, refund_service


def _generate_return_number(org_id: int) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    return f"RET-{org_id}-{stamp}-{uuid.uuid4().hex[:6].upper()}"


def _to_return_out(db: Session, ret: OrderReturn) -> ReturnOut:
    order = db.get(Order, ret.order_id)
    items = list(
        db.scalars(
            select(OrderReturnItem)
            .where(
                OrderReturnItem.return_id == ret.id,
                OrderReturnItem.organisation_id == ret.organisation_id,
            )
            .order_by(OrderReturnItem.id.asc())
        ).all()
    )
    prod_ids = [i.product_id for i in items]
    prods = (
        {
            p.id: p
            for p in db.scalars(
                select(CommerceProduct).where(CommerceProduct.id.in_(prod_ids))
            ).all()
        }
        if prod_ids
        else {}
    )
    return ReturnOut(
        id=str(ret.id),
        organisation_id=ret.organisation_id,
        return_number=ret.return_number,
        order_id=str(ret.order_id),
        order_number=order.order_number if order else f"Order #{ret.order_id}",
        customer_id=ret.customer_id,
        return_type=ret.return_type,
        status=ret.status,
        reason=ret.reason,
        condition=ret.condition,
        restock_approved=ret.restock_approved,
        refund_amount_minor=ret.refund_amount_minor,
        refund_amount=format_minor_to_decimal_str(ret.refund_amount_minor),
        refund_id=str(ret.refund_id) if ret.refund_id else None,
        exchange_order_id=str(ret.exchange_order_id) if ret.exchange_order_id else None,
        requested_by=ret.requested_by,
        reviewed_by=ret.reviewed_by,
        items=[
            ReturnItemOut(
                id=str(it.id),
                order_item_id=it.order_item_id,
                product_id=str(it.product_id),
                product_name=prods[it.product_id].name if it.product_id in prods else f"Product #{it.product_id}",
                sku=prods[it.product_id].sku if it.product_id in prods else "",
                quantity=it.quantity,
                condition=it.condition,
                restocked=it.restocked,
            )
            for it in items
        ],
        created_at=ret.created_at,
    )


def create_return_request(
    db: Session, org_ctx: OrgContext, payload: ReturnCreate
) -> ReturnOut:
    org_id = org_ctx.organisation.id
    order = db.scalar(
        select(Order).where(Order.id == payload.order_id, Order.organisation_id == org_id)
    )
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found.")
    if order.order_status not in ("PAID", "PROCESSING", "FULFILLED"):
        raise HTTPException(
            status_code=409,
            detail=f"Returns can only be requested for PAID, PROCESSING, or FULFILLED orders (current: {order.order_status}).",
        )

    order_items = {
        oi.id: oi
        for oi in db.scalars(
            select(OrderItem).where(
                OrderItem.order_id == order.id,
                OrderItem.organisation_id == org_id,
            )
        ).all()
    }

    already_returned_rows = db.execute(
        select(
            OrderReturnItem.order_item_id,
            func.coalesce(func.sum(OrderReturnItem.quantity), 0).label("qty"),
        )
        .join(OrderReturn, OrderReturn.id == OrderReturnItem.return_id)
        .where(
            OrderReturn.organisation_id == org_id,
            OrderReturn.order_id == order.id,
            OrderReturn.status != "REJECTED",
        )
        .group_by(OrderReturnItem.order_item_id)
    ).all()
    already_returned = {int(r.order_item_id): int(r.qty or 0) for r in already_returned_rows}

    refund_amount_minor = 0
    prepared: list[tuple[OrderItem, int, str]] = []
    seen_oi: set[int] = set()
    for item in payload.items:
        if item.order_item_id in seen_oi:
            raise HTTPException(status_code=422, detail="Duplicate order_item_id in return request.")
        seen_oi.add(item.order_item_id)
        oi = order_items.get(item.order_item_id)
        if oi is None:
            raise HTTPException(status_code=404, detail=f"Order item {item.order_item_id} not found.")
        remaining = oi.quantity - already_returned.get(oi.id, 0)
        if item.quantity > remaining:
            raise HTTPException(
                status_code=409,
                detail=f"Cannot return {item.quantity} units of SKU {oi.sku_snapshot}; only {remaining} returnable.",
            )
        per_unit_total = oi.line_total_minor // oi.quantity
        refund_amount_minor += per_unit_total * item.quantity
        prepared.append((oi, item.quantity, item.condition))

    dominant_condition = prepared[0][2]
    if any(c in ("damaged", "defective") for _, _, c in prepared):
        dominant_condition = "damaged"

    ret = OrderReturn(
        organisation_id=org_id,
        return_number=_generate_return_number(org_id),
        order_id=order.id,
        customer_id=order.customer_id,
        return_type=payload.return_type,
        status="REQUESTED",
        reason=payload.reason.strip(),
        condition=dominant_condition,
        restock_approved=False,
        refund_amount_minor=min(refund_amount_minor, order.total_minor),
        requested_by=org_ctx.user.email,
    )
    db.add(ret)
    db.flush()

    for oi, qty, cond in prepared:
        db.add(
            OrderReturnItem(
                organisation_id=org_id,
                return_id=ret.id,
                order_item_id=oi.id,
                product_id=oi.product_id,
                quantity=qty,
                condition=cond,
                restocked=False,
            )
        )

    db.add(
        AuditLog(
            organisation_id=org_id,
            actor_type=org_ctx.membership.role,
            actor_ref=org_ctx.user.email,
            action="order_return_requested",
            entity_name="order_returns",
            entity_id=str(ret.id),
            details={
                "return_number": ret.return_number,
                "order_id": order.id,
                "return_type": ret.return_type,
                "refund_amount_minor": ret.refund_amount_minor,
            },
        )
    )
    db.commit()
    db.refresh(ret)
    return _to_return_out(db, ret)


def list_returns(db: Session, org_id: int, status: str | None = None) -> list[ReturnOut]:
    stmt = select(OrderReturn).where(OrderReturn.organisation_id == org_id)
    if status:
        stmt = stmt.where(OrderReturn.status == status.upper())
    rows = db.scalars(stmt.order_by(OrderReturn.id.desc())).all()
    return [_to_return_out(db, r) for r in rows]


def review_return(
    db: Session,
    org_ctx: OrgContext,
    return_id: int,
    payload: ReturnReviewRequest,
) -> ReturnOut:
    org_id = org_ctx.organisation.id
    ret = db.scalar(
        select(OrderReturn)
        .where(
            OrderReturn.id == return_id,
            OrderReturn.organisation_id == org_id,
        )
        .with_for_update()
    )
    if ret is None:
        raise HTTPException(status_code=404, detail="Return request not found.")
    if ret.status in ("REJECTED", "COMPLETED"):
        raise HTTPException(status_code=409, detail=f"Return in status {ret.status} is already finalized.")

    now = datetime.now(timezone.utc)
    if payload.decision == "REJECTED":
        ret.status = "REJECTED"
        ret.reviewed_by = org_ctx.user.email
        ret.reviewed_at = now
        ret.updated_at = now
        db.add(
            AuditLog(
                organisation_id=org_id,
                actor_type=org_ctx.membership.role,
                actor_ref=org_ctx.user.email,
                action="order_return_rejected",
                entity_name="order_returns",
                entity_id=str(ret.id),
                details={"return_number": ret.return_number, "note": payload.note},
            )
        )
        db.commit()
        db.refresh(ret)
        return _to_return_out(db, ret)

    # APPROVED or COMPLETED
    ret_items = list(
        db.scalars(
            select(OrderReturnItem)
            .where(
                OrderReturnItem.return_id == ret.id,
                OrderReturnItem.organisation_id == org_id,
            )
            .with_for_update()
        ).all()
    )

    if payload.decision == "COMPLETED" or payload.restock_approved:
        ret.restock_approved = payload.restock_approved
        for ri in ret_items:
            if ri.restocked:
                continue
            oi = db.get(OrderItem, ri.order_item_id)
            if oi is None:
                continue
            bal = inventory_service._get_or_create_balance_locked(
                db, org_id, ri.product_id, oi.location_id
            )
            if payload.restock_approved and ri.condition in ("unopened", "good"):
                bal.quantity += ri.quantity
                bal.last_movement_at = now
                bal.updated_at = now
                ri.restocked = True
                db.add(
                    InventoryMovement(
                        organisation_id=org_id,
                        balance_id=bal.id,
                        product_id=ri.product_id,
                        location_id=oi.location_id,
                        movement_type="return_restock",
                        quantity_delta=ri.quantity,
                        reserved_delta=0,
                        balance_after=bal.quantity,
                        reserved_after=bal.reserved_quantity,
                        reference_type="order_return",
                        reference_id=ret.return_number,
                        reason=f"Approved return restock ({ri.condition})",
                        actor_ref=org_ctx.user.email,
                    )
                )
            elif payload.decision == "COMPLETED" and ri.condition in ("damaged", "defective"):
                bal.damaged_quantity += ri.quantity
                bal.last_movement_at = now
                bal.updated_at = now
                ri.restocked = True
                db.add(
                    InventoryMovement(
                        organisation_id=org_id,
                        balance_id=bal.id,
                        product_id=ri.product_id,
                        location_id=oi.location_id,
                        movement_type="damaged",
                        quantity_delta=0,
                        reserved_delta=0,
                        balance_after=bal.quantity,
                        reserved_after=bal.reserved_quantity,
                        reference_type="order_return",
                        reference_id=ret.return_number,
                        reason=f"Returned item quarantined as {ri.condition} (not restocked to sellable inventory)",
                        actor_ref=org_ctx.user.email,
                    )
                )

    ret.status = payload.decision
    ret.reviewed_by = org_ctx.user.email
    ret.reviewed_at = now
    if payload.decision == "COMPLETED":
        ret.completed_at = now
        from app.services import india_tax_service

        india_tax_service.generate_credit_note_for_return(db, org_id, ret.id)
    ret.updated_at = now

    if payload.trigger_refund and ret.refund_id is None and ret.refund_amount_minor > 0:
        cap_tx = db.scalar(
            select(PaymentTransaction)
            .where(
                PaymentTransaction.organisation_id == org_id,
                PaymentTransaction.order_id == ret.order_id,
                PaymentTransaction.status == "CAPTURED",
            )
            .order_by(PaymentTransaction.id.desc())
            .limit(1)
        )
        if cap_tx is not None:
            refund_out = refund_service.request_refund(
                db,
                org_ctx,
                cap_tx.id,
                RefundCreateRequest(
                    amount_minor=ret.refund_amount_minor,
                    reason=f"Return {ret.return_number}: {ret.reason}",
                    speed="normal",
                ),
                idempotency_key=f"return-{ret.return_number}",
            )
            ret = db.get(OrderReturn, ret.id) or ret
            ret.refund_id = int(refund_out.id)

    db.add(
        AuditLog(
            organisation_id=org_id,
            actor_type=org_ctx.membership.role,
            actor_ref=org_ctx.user.email,
            action=f"order_return_{payload.decision.lower()}",
            entity_name="order_returns",
            entity_id=str(ret.id),
            details={
                "return_number": ret.return_number,
                "restock_approved": ret.restock_approved,
                "refund_id": ret.refund_id,
            },
        )
    )
    db.commit()
    db.refresh(ret)
    return _to_return_out(db, ret)
