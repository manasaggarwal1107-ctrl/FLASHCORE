from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.campaigns import SurgeCampaign
from app.models.finance import PaymentApprovalRequest
from app.models.operations import Notification, OrderReturn
from app.models.procurement import PurchaseOrder
from app.models.retail import CommerceProduct, InventoryBalance, Order
from app.schemas.expansion import NotificationOut


def _to_out(n: Notification) -> NotificationOut:
    return NotificationOut(
        id=str(n.id),
        category=n.category,
        severity=n.severity,
        title=n.title,
        message=n.message,
        entity_type=n.entity_type,
        entity_id=n.entity_id,
        is_read=n.is_read,
        read_at=n.read_at,
        created_at=n.created_at,
    )


def _create_if_new(
    db: Session,
    org_id: int,
    *,
    category: str,
    severity: str,
    title: str,
    message: str,
    entity_type: str,
    entity_id: str,
    dedupe_key: str,
) -> None:
    existing = db.scalar(
        select(Notification).where(
            Notification.organisation_id == org_id,
            Notification.dedupe_key == dedupe_key,
            Notification.is_read.is_(False),
        )
    )
    if existing is None:
        db.add(
            Notification(
                organisation_id=org_id,
                category=category,
                severity=severity,
                title=title,
                message=message,
                entity_type=entity_type,
                entity_id=entity_id,
                dedupe_key=dedupe_key,
            )
        )


def sync_operational_alerts(db: Session, org_id: int) -> None:
    now = datetime.now(timezone.utc)

    # 1. Low-stock alerts
    low_rows = db.execute(
        select(
            CommerceProduct.id,
            CommerceProduct.sku,
            CommerceProduct.name,
            InventoryBalance.quantity,
            InventoryBalance.reserved_quantity,
            InventoryBalance.low_stock_threshold,
        )
        .join(CommerceProduct, CommerceProduct.id == InventoryBalance.product_id)
        .where(
            InventoryBalance.organisation_id == org_id,
            (InventoryBalance.quantity - InventoryBalance.reserved_quantity) <= InventoryBalance.low_stock_threshold,
        )
        .limit(20)
    ).all()
    for row in low_rows:
        avail = max(0, int(row.quantity) - int(row.reserved_quantity))
        _create_if_new(
            db,
            org_id,
            category="low_stock",
            severity="critical" if avail == 0 else "warning",
            title=f"{'Out of stock' if avail == 0 else 'Low stock'}: {row.sku}",
            message=f"{row.name} has {avail} available units (threshold {row.low_stock_threshold}).",
            entity_type="commerce_products",
            entity_id=str(row.id),
            dedupe_key=f"low_stock:{row.id}:{avail == 0}",
        )

    # 2. Pending refund approvals
    pending_refunds = db.scalars(
        select(PaymentApprovalRequest)
        .where(
            PaymentApprovalRequest.organisation_id == org_id,
            PaymentApprovalRequest.status == "PENDING",
        )
        .limit(10)
    ).all()
    for req in pending_refunds:
        _create_if_new(
            db,
            org_id,
            category="refund",
            severity="warning",
            title=f"Refund approval pending (#{req.refund_id})",
            message=f"High-value refund request awaits owner/admin approval.",
            entity_type="payment_refunds",
            entity_id=str(req.refund_id),
            dedupe_key=f"refund_approval:{req.id}",
        )

    # 3. Pending return requests
    pending_returns = db.scalars(
        select(OrderReturn)
        .where(
            OrderReturn.organisation_id == org_id,
            OrderReturn.status == "REQUESTED",
        )
        .limit(10)
    ).all()
    for ret in pending_returns:
        _create_if_new(
            db,
            org_id,
            category="return",
            severity="info",
            title=f"Return request {ret.return_number}",
            message=f"Return/exchange request awaits review.",
            entity_type="order_returns",
            entity_id=str(ret.id),
            dedupe_key=f"return_request:{ret.id}",
        )

    # 4. Expiring campaigns (<24h)
    soon = now + timedelta(hours=24)
    expiring = db.scalars(
        select(SurgeCampaign)
        .where(
            SurgeCampaign.organisation_id == org_id,
            SurgeCampaign.status == "ACTIVE",
            SurgeCampaign.ends_at <= soon,
        )
        .limit(10)
    ).all()
    for c in expiring:
        _create_if_new(
            db,
            org_id,
            category="campaign",
            severity="info",
            title=f"Surge campaign ending soon: {c.name}",
            message=f"Campaign ends at {c.ends_at.isoformat()}.",
            entity_type="surge_campaigns",
            entity_id=str(c.id),
            dedupe_key=f"campaign_ending:{c.id}",
        )

    # 5. Open Purchase Orders
    open_pos = db.scalars(
        select(PurchaseOrder)
        .where(
            PurchaseOrder.organisation_id == org_id,
            PurchaseOrder.status.in_(("SUBMITTED", "PARTIALLY_RECEIVED")),
        )
        .limit(10)
    ).all()
    for po in open_pos:
        _create_if_new(
            db,
            org_id,
            category="purchase_order",
            severity="info",
            title=f"PO awaiting receipt: {po.po_number}",
            message=f"Purchase order status is {po.status}.",
            entity_type="purchase_orders",
            entity_id=str(po.id),
            dedupe_key=f"po_open:{po.id}:{po.status}",
        )

    # 6. Pending payment orders
    pending_orders = db.scalars(
        select(Order)
        .where(
            Order.organisation_id == org_id,
            Order.order_status == "PENDING_PAYMENT",
        )
        .limit(10)
    ).all()
    for o in pending_orders:
        _create_if_new(
            db,
            org_id,
            category="pending_order",
            severity="info",
            title=f"Order awaiting payment: {o.order_number}",
            message="Order has active inventory reservations pending payment.",
            entity_type="orders",
            entity_id=str(o.id),
            dedupe_key=f"pending_order:{o.id}",
        )

    db.flush()


def list_notifications(db: Session, org_id: int, unread_only: bool = False) -> dict:
    sync_operational_alerts(db, org_id)
    db.commit()

    stmt = select(Notification).where(Notification.organisation_id == org_id)
    if unread_only:
        stmt = stmt.where(Notification.is_read.is_(False))
    items = db.scalars(stmt.order_by(Notification.is_read.asc(), Notification.id.desc()).limit(50)).all()
    unread_count = int(
        db.scalar(
            select(func.count(Notification.id)).where(
                Notification.organisation_id == org_id,
                Notification.is_read.is_(False),
            )
        )
        or 0
    )
    return {
        "unread_count": unread_count,
        "items": [_to_out(n) for n in items],
    }


def mark_notification_read(db: Session, org_id: int, notification_id: int) -> NotificationOut | None:
    n = db.scalar(
        select(Notification).where(
            Notification.id == notification_id,
            Notification.organisation_id == org_id,
        )
    )
    if n is None:
        return None
    n.is_read = True
    n.read_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(n)
    return _to_out(n)
