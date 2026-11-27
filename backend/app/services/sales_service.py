from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.finance import PaymentRefund
from app.models.operations import SalesRecord
from app.models.payments import PaymentTransaction
from app.models.retail import (
    CommerceProduct,
    InventoryBalance,
    InventoryLocation,
    Order,
    OrderItem,
)
from app.schemas.expansion import SalesDashboardOut, SalesRecordOut
from app.schemas.retail import format_minor_to_decimal_str


def sync_sales_record_for_order(
    db: Session,
    order: Order,
    *,
    transaction_ref: str | None = None,
) -> SalesRecord | None:
    """Create or update a traceable SalesRecord once an order has confirmed payment."""
    if order.order_status in ("CANCELLED", "EXPIRED") or order.payment_status != "CAPTURED":
        return None

    existing = db.scalar(
        select(SalesRecord).where(
            SalesRecord.organisation_id == order.organisation_id,
            SalesRecord.order_id == order.id,
        )
    )
    first_item = db.scalar(
        select(OrderItem)
        .where(OrderItem.order_id == order.id)
        .order_by(OrderItem.id.asc())
        .limit(1)
    )
    if not transaction_ref:
        transaction_ref = db.scalar(
            select(PaymentTransaction.provider_payment_id)
            .where(
                PaymentTransaction.organisation_id == order.organisation_id,
                PaymentTransaction.order_id == order.id,
            )
            .order_by(PaymentTransaction.id.desc())
            .limit(1)
        ) or order.order_number

    cust_name = (
        order.customer_snapshot.get("name")
        if isinstance(order.customer_snapshot, dict)
        else None
    )

    if existing is None:
        rec = SalesRecord(
            organisation_id=order.organisation_id,
            transaction_ref=transaction_ref,
            order_id=order.id,
            order_number=order.order_number,
            customer_id=order.customer_id,
            customer_name=cust_name,
            location_id=first_item.location_id if first_item else None,
            campaign_id=order.campaign_id,
            gross_amount_minor=order.subtotal_minor,
            discount_minor=order.discount_minor,
            tax_minor=order.tax_minor,
            net_amount_minor=order.total_minor,
            refunded_minor=0,
            currency=order.currency,
            payment_status=order.payment_status,
            refund_status="NONE",
            sold_at=order.placed_at,
        )
        db.add(rec)
        db.flush()
        return rec

    existing.payment_status = order.payment_status
    existing.transaction_ref = transaction_ref
    existing.updated_at = datetime.now(timezone.utc)
    return existing


def sync_refund_to_sales_record(db: Session, org_id: int, order_id: int) -> None:
    rec = db.scalar(
        select(SalesRecord).where(
            SalesRecord.organisation_id == org_id,
            SalesRecord.order_id == order_id,
        )
    )
    if rec is None:
        return

    refunded_sum = int(
        db.scalar(
            select(func.coalesce(func.sum(PaymentRefund.amount_minor), 0)).where(
                PaymentRefund.organisation_id == org_id,
                PaymentRefund.order_id == order_id,
                PaymentRefund.status == "PROCESSED",
            )
        )
        or 0
    )
    rec.refunded_minor = refunded_sum
    if refunded_sum <= 0:
        rec.refund_status = "NONE"
    elif refunded_sum >= rec.net_amount_minor:
        rec.refund_status = "FULL"
    else:
        rec.refund_status = "PARTIAL"
    rec.updated_at = datetime.now(timezone.utc)


def to_sales_record_out(rec: SalesRecord) -> SalesRecordOut:
    return SalesRecordOut(
        id=str(rec.id),
        organisation_id=rec.organisation_id,
        transaction_ref=rec.transaction_ref,
        order_id=str(rec.order_id),
        order_number=rec.order_number,
        customer_id=rec.customer_id,
        customer_name=rec.customer_name,
        location_id=rec.location_id,
        campaign_id=rec.campaign_id,
        gross_amount_minor=rec.gross_amount_minor,
        gross_amount=format_minor_to_decimal_str(rec.gross_amount_minor),
        discount_minor=rec.discount_minor,
        discount=format_minor_to_decimal_str(rec.discount_minor),
        tax_minor=rec.tax_minor,
        tax=format_minor_to_decimal_str(rec.tax_minor),
        net_amount_minor=rec.net_amount_minor,
        net_amount=format_minor_to_decimal_str(rec.net_amount_minor),
        refunded_minor=rec.refunded_minor,
        refunded=format_minor_to_decimal_str(rec.refunded_minor),
        currency=rec.currency,
        payment_status=rec.payment_status,
        refund_status=rec.refund_status,
        sold_at=rec.sold_at,
    )


def list_sales_records(
    db: Session,
    org_id: int,
    *,
    page: int = 1,
    page_size: int = 25,
    search: str | None = None,
    refund_status: str | None = None,
) -> dict:
    stmt = select(SalesRecord).where(SalesRecord.organisation_id == org_id)
    if search and search.strip():
        pattern = f"%{search.strip()}%"
        stmt = stmt.where(
            (SalesRecord.order_number.ilike(pattern))
            | (SalesRecord.transaction_ref.ilike(pattern))
            | (SalesRecord.customer_name.ilike(pattern))
        )
    if refund_status:
        stmt = stmt.where(SalesRecord.refund_status == refund_status.upper())

    total = int(
        db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    )
    rows = db.scalars(
        stmt.order_by(SalesRecord.sold_at.desc(), SalesRecord.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return {
        "items": [to_sales_record_out(r) for r in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


def get_sales_dashboard(db: Session, org_id: int, days: int = 30) -> SalesDashboardOut:
    now = datetime.now(timezone.utc)
    start_today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    period_start = now - timedelta(days=days)
    prev_start = period_start - timedelta(days=days)

    records = list(
        db.scalars(
            select(SalesRecord)
            .where(SalesRecord.organisation_id == org_id)
            .order_by(SalesRecord.sold_at.desc(), SalesRecord.id.desc())
        ).all()
    )

    active_records = [r for r in records if r.refund_status != "FULL"]
    today_minor = sum(
        max(0, r.net_amount_minor - r.refunded_minor)
        for r in records
        if r.sold_at >= start_today
    )
    total_gross_net = sum(r.net_amount_minor for r in records)
    total_after_refunds = sum(max(0, r.net_amount_minor - r.refunded_minor) for r in records)
    order_count = len(active_records)
    aov_minor = total_after_refunds // order_count if order_count > 0 else 0

    curr_rev = sum(
        max(0, r.net_amount_minor - r.refunded_minor)
        for r in records
        if r.sold_at >= period_start
    )
    prev_rev = sum(
        max(0, r.net_amount_minor - r.refunded_minor)
        for r in records
        if prev_start <= r.sold_at < period_start
    )
    rev_delta = (
        round(((curr_rev - prev_rev) / prev_rev) * 100.0, 2)
        if prev_rev > 0
        else None
    )

    valid_order_ids = [r.order_id for r in records if r.refund_status != "FULL"]
    top_products: list[dict] = []
    slow_products: list[dict] = []
    sales_by_category: list[dict] = []
    sales_by_location: list[dict] = []
    top_sku_share: float | None = None

    if valid_order_ids:
        item_rows = db.execute(
            select(
                OrderItem.product_id,
                OrderItem.sku_snapshot,
                OrderItem.name_snapshot,
                func.coalesce(func.sum(OrderItem.quantity), 0).label("units"),
                func.coalesce(func.sum(OrderItem.line_total_minor), 0).label("revenue_minor"),
                CommerceProduct.category,
            )
            .join(CommerceProduct, CommerceProduct.id == OrderItem.product_id)
            .where(
                OrderItem.organisation_id == org_id,
                OrderItem.order_id.in_(valid_order_ids),
            )
            .group_by(
                OrderItem.product_id,
                OrderItem.sku_snapshot,
                OrderItem.name_snapshot,
                CommerceProduct.category,
            )
        ).all()

        sorted_top = sorted(item_rows, key=lambda x: int(x.revenue_minor or 0), reverse=True)
        total_item_rev = sum(int(x.revenue_minor or 0) for x in sorted_top)
        if sorted_top and total_item_rev > 0:
            top_sku_share = round(
                (int(sorted_top[0].revenue_minor or 0) / total_item_rev) * 100.0, 2
            )

        for row in sorted_top[:10]:
            rev = int(row.revenue_minor or 0)
            top_products.append(
                {
                    "product_id": str(row.product_id),
                    "sku": row.sku_snapshot,
                    "name": row.name_snapshot,
                    "category": row.category or "Uncategorized",
                    "units_sold": int(row.units or 0),
                    "revenue_minor": rev,
                    "revenue": format_minor_to_decimal_str(rev),
                }
            )

        cat_agg: dict[str, int] = {}
        for row in item_rows:
            cat = row.category or "Uncategorized"
            cat_agg[cat] = cat_agg.get(cat, 0) + int(row.revenue_minor or 0)
        sales_by_category = [
            {"category": k, "revenue_minor": v, "revenue": format_minor_to_decimal_str(v)}
            for k, v in sorted(cat_agg.items(), key=lambda x: x[1], reverse=True)
        ]

        loc_rows = db.execute(
            select(
                InventoryLocation.name,
                func.coalesce(func.sum(OrderItem.line_total_minor), 0).label("revenue_minor"),
                func.coalesce(func.sum(OrderItem.quantity), 0).label("units"),
            )
            .join(InventoryLocation, InventoryLocation.id == OrderItem.location_id)
            .where(
                OrderItem.organisation_id == org_id,
                OrderItem.order_id.in_(valid_order_ids),
            )
            .group_by(InventoryLocation.name)
        ).all()
        sales_by_location = [
            {
                "location": r.name,
                "units": int(r.units or 0),
                "revenue_minor": int(r.revenue_minor or 0),
                "revenue": format_minor_to_decimal_str(int(r.revenue_minor or 0)),
            }
            for r in loc_rows
        ]

    # Slow products from catalog with low/zero units sold
    sold_by_pid = {int(p["product_id"]): int(p["units_sold"]) for p in top_products}
    all_prods = db.scalars(
        select(CommerceProduct).where(CommerceProduct.organisation_id == org_id).limit(50)
    ).all()
    for p in all_prods:
        u = sold_by_pid.get(p.id, 0)
        if u == 0:
            slow_products.append(
                {
                    "product_id": str(p.id),
                    "sku": p.sku,
                    "name": p.name,
                    "units_sold": 0,
                }
            )

    day_buckets: dict[str, int] = {}
    for r in records:
        dkey = r.sold_at.strftime("%Y-%m-%d")
        day_buckets[dkey] = day_buckets.get(dkey, 0) + max(0, r.net_amount_minor - r.refunded_minor)
    trend = [
        {"date": k, "revenue_minor": v, "revenue": format_minor_to_decimal_str(v)}
        for k, v in sorted(day_buckets.items())
    ]

    # Repeat customer rate
    cust_counts: dict[int, int] = {}
    for r in active_records:
        if r.customer_id:
            cust_counts[r.customer_id] = cust_counts.get(r.customer_id, 0) + 1
    repeat_rate = (
        round((sum(1 for c in cust_counts.values() if c > 1) / len(cust_counts)) * 100.0, 2)
        if cust_counts
        else None
    )

    on_hand_total = int(
        db.scalar(
            select(func.coalesce(func.sum(InventoryBalance.quantity), 0)).where(
                InventoryBalance.organisation_id == org_id
            )
        )
        or 0
    )
    units_sold_total = sum(int(p["units_sold"]) for p in top_products)
    turnover = (
        round(units_sold_total / on_hand_total, 3) if on_hand_total > 0 and units_sold_total > 0 else None
    )

    return SalesDashboardOut(
        today_sales_minor=today_minor,
        today_sales=format_minor_to_decimal_str(today_minor),
        total_revenue_minor=total_gross_net,
        total_revenue=format_minor_to_decimal_str(total_gross_net),
        net_revenue_after_refunds_minor=total_after_refunds,
        net_revenue_after_refunds=format_minor_to_decimal_str(total_after_refunds),
        order_count=order_count,
        average_order_value_minor=aov_minor,
        average_order_value=format_minor_to_decimal_str(aov_minor),
        previous_period_revenue_minor=prev_rev,
        previous_period_revenue=format_minor_to_decimal_str(prev_rev),
        revenue_delta_percent=rev_delta,
        top_products=top_products,
        slow_products=slow_products[:10],
        sales_by_category=sales_by_category,
        sales_by_location=sales_by_location,
        trend=trend,
        recent_transactions=[to_sales_record_out(r) for r in records[:10]],
        repeat_customer_rate_percent=repeat_rate,
        inventory_turnover_ratio=turnover,
        top_sku_concentration_percent=top_sku_share,
    )
