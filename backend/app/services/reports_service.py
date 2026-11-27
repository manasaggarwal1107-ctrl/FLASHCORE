from datetime import datetime
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.csv_utils import render_csv
from app.models.campaigns import PromotionRedemption, SurgeCampaign
from app.models.finance import PaymentRefund
from app.models.operations import SalesRecord
from app.models.payments import PaymentTransaction
from app.models.procurement import PurchaseOrder, Supplier
from app.models.retail import (
    CommerceProduct,
    Customer,
    InventoryBalance,
    InventoryLocation,
    InventoryMovement,
    Order,
    OrderItem,
)
from app.schemas.retail import format_minor_to_decimal_str


def _within_dates(col, start_at: datetime | None, end_at: datetime | None):
    clauses = []
    if start_at is not None:
        clauses.append(col >= start_at)
    if end_at is not None:
        clauses.append(col <= end_at)
    return clauses


def generate_report(
    db: Session,
    org_id: int,
    report_type: str,
    *,
    start_at: datetime | None = None,
    end_at: datetime | None = None,
) -> tuple[list[str], list[list[object]], list[dict]]:
    rtype = report_type.lower().strip()

    if rtype == "sales":
        stmt = select(SalesRecord).where(
            SalesRecord.organisation_id == org_id,
            *_within_dates(SalesRecord.sold_at, start_at, end_at),
        ).order_by(SalesRecord.sold_at.desc())
        rows = db.scalars(stmt).all()
        headers = [
            "Transaction Ref",
            "Order Number",
            "Customer",
            "Gross (INR)",
            "Discount (INR)",
            "Tax (INR)",
            "Net (INR)",
            "Refunded (INR)",
            "Payment Status",
            "Refund Status",
            "Sold At",
        ]
        table = [
            [
                r.transaction_ref,
                r.order_number,
                r.customer_name or "Walk-in",
                format_minor_to_decimal_str(r.gross_amount_minor),
                format_minor_to_decimal_str(r.discount_minor),
                format_minor_to_decimal_str(r.tax_minor),
                format_minor_to_decimal_str(r.net_amount_minor),
                format_minor_to_decimal_str(r.refunded_minor),
                r.payment_status,
                r.refund_status,
                r.sold_at.isoformat(),
            ]
            for r in rows
        ]
    elif rtype == "product_performance":
        stmt = (
            select(
                OrderItem.sku_snapshot,
                OrderItem.name_snapshot,
                func.coalesce(func.sum(OrderItem.quantity), 0).label("units"),
                func.coalesce(func.sum(OrderItem.line_total_minor), 0).label("rev_minor"),
            )
            .join(Order, Order.id == OrderItem.order_id)
            .where(
                OrderItem.organisation_id == org_id,
                Order.order_status.in_(("PAID", "PROCESSING", "FULFILLED")),
                *_within_dates(Order.placed_at, start_at, end_at),
            )
            .group_by(OrderItem.sku_snapshot, OrderItem.name_snapshot)
            .order_by(func.sum(OrderItem.line_total_minor).desc())
        )
        rows = db.execute(stmt).all()
        headers = ["SKU", "Product", "Units Sold", "Gross Revenue (INR)"]
        table = [
            [r.sku_snapshot, r.name_snapshot, int(r.units or 0), format_minor_to_decimal_str(int(r.rev_minor or 0))]
            for r in rows
        ]
    elif rtype == "inventory":
        rows = db.execute(
            select(
                CommerceProduct.sku,
                CommerceProduct.name,
                InventoryLocation.name.label("location_name"),
                InventoryBalance.quantity,
                InventoryBalance.reserved_quantity,
                InventoryBalance.damaged_quantity,
                InventoryBalance.low_stock_threshold,
                CommerceProduct.price_minor,
            )
            .join(CommerceProduct, CommerceProduct.id == InventoryBalance.product_id)
            .join(InventoryLocation, InventoryLocation.id == InventoryBalance.location_id)
            .where(InventoryBalance.organisation_id == org_id)
            .order_by(CommerceProduct.sku.asc())
        ).all()
        headers = ["SKU", "Product", "Location", "On Hand", "Reserved", "Available", "Damaged", "Threshold", "Retail Value (INR)"]
        table = [
            [
                r.sku,
                r.name,
                r.location_name,
                r.quantity,
                r.reserved_quantity,
                max(0, r.quantity - r.reserved_quantity),
                r.damaged_quantity,
                r.low_stock_threshold,
                format_minor_to_decimal_str(r.quantity * r.price_minor),
            ]
            for r in rows
        ]
    elif rtype == "stock_movements":
        rows = db.execute(
            select(
                InventoryMovement.id,
                CommerceProduct.sku,
                InventoryLocation.name.label("location_name"),
                InventoryMovement.movement_type,
                InventoryMovement.quantity_delta,
                InventoryMovement.balance_after,
                InventoryMovement.reason,
                InventoryMovement.actor_ref,
                InventoryMovement.created_at,
            )
            .join(CommerceProduct, CommerceProduct.id == InventoryMovement.product_id)
            .join(InventoryLocation, InventoryLocation.id == InventoryMovement.location_id)
            .where(
                InventoryMovement.organisation_id == org_id,
                *_within_dates(InventoryMovement.created_at, start_at, end_at),
            )
            .order_by(InventoryMovement.id.desc())
        ).all()
        headers = ["ID", "SKU", "Location", "Type", "Delta", "Balance After", "Reason", "Actor", "Occurred At"]
        table = [
            [
                r.id,
                r.sku,
                r.location_name,
                r.movement_type,
                r.quantity_delta,
                r.balance_after,
                r.reason or "",
                r.actor_ref or "",
                r.created_at.isoformat(),
            ]
            for r in rows
        ]
    elif rtype == "customers":
        rows = db.execute(
            select(
                Customer.id,
                Customer.name,
                Customer.email,
                Customer.phone,
                func.count(SalesRecord.id).label("orders"),
                func.coalesce(func.sum(SalesRecord.net_amount_minor - SalesRecord.refunded_minor), 0).label("ltv"),
            )
            .outerjoin(SalesRecord, SalesRecord.customer_id == Customer.id)
            .where(Customer.organisation_id == org_id)
            .group_by(Customer.id, Customer.name, Customer.email, Customer.phone)
            .order_by(func.coalesce(func.sum(SalesRecord.net_amount_minor), 0).desc())
        ).all()
        headers = ["Customer ID", "Name", "Email", "Phone", "Paid Orders", "Lifetime Spend (INR)", "Segment"]
        table = []
        for r in rows:
            orders = int(r.orders or 0)
            ltv = int(r.ltv or 0)
            seg = "VIP" if orders >= 3 or ltv >= 500000 else ("Repeat" if orders >= 2 else ("Buyer" if orders == 1 else "Lead"))
            table.append([f"CUST-{r.id:05d}", r.name, r.email or "", r.phone or "", orders, format_minor_to_decimal_str(ltv), seg])
    elif rtype == "campaigns":
        rows = db.execute(
            select(
                SurgeCampaign.id,
                SurgeCampaign.name,
                SurgeCampaign.status,
                SurgeCampaign.total_units_sold,
                func.count(SalesRecord.id).label("orders"),
                func.coalesce(func.sum(SalesRecord.net_amount_minor), 0).label("rev_minor"),
                func.coalesce(func.sum(SalesRecord.discount_minor), 0).label("disc_minor"),
            )
            .outerjoin(SalesRecord, SalesRecord.campaign_id == SurgeCampaign.id)
            .where(SurgeCampaign.organisation_id == org_id)
            .group_by(SurgeCampaign.id, SurgeCampaign.name, SurgeCampaign.status, SurgeCampaign.total_units_sold)
            .order_by(SurgeCampaign.id.desc())
        ).all()
        headers = ["Campaign ID", "Name", "Status", "Units Sold", "Paid Orders", "Revenue (INR)", "Discounts (INR)"]
        table = [
            [
                r.id,
                r.name,
                r.status,
                r.total_units_sold,
                int(r.orders or 0),
                format_minor_to_decimal_str(int(r.rev_minor or 0)),
                format_minor_to_decimal_str(int(r.disc_minor or 0)),
            ]
            for r in rows
        ]
    elif rtype == "payments":
        rows = db.scalars(
            select(PaymentTransaction)
            .where(
                PaymentTransaction.organisation_id == org_id,
                *_within_dates(PaymentTransaction.created_at, start_at, end_at),
            )
            .order_by(PaymentTransaction.id.desc())
        ).all()
        headers = ["ID", "Provider Payment ID", "Order ID", "Event", "Status", "Method", "Amount (INR)", "Created At"]
        table = [
            [
                r.id,
                r.provider_payment_id,
                r.order_id,
                r.event_type,
                r.status,
                r.method or "",
                format_minor_to_decimal_str(r.amount_minor),
                r.created_at.isoformat(),
            ]
            for r in rows
        ]
    elif rtype == "refunds":
        rows = db.scalars(
            select(PaymentRefund)
            .where(
                PaymentRefund.organisation_id == org_id,
                *_within_dates(PaymentRefund.created_at, start_at, end_at),
            )
            .order_by(PaymentRefund.id.desc())
        ).all()
        headers = ["Refund ID", "Order ID", "Amount (INR)", "Status", "Reason", "Created At"]
        table = [
            [r.id, r.order_id, format_minor_to_decimal_str(r.amount_minor), r.status, r.reason, r.created_at.isoformat()]
            for r in rows
        ]
    elif rtype == "procurement":
        rows = db.execute(
            select(
                PurchaseOrder.po_number,
                Supplier.name.label("supplier_name"),
                PurchaseOrder.status,
                PurchaseOrder.total_cost_minor,
                PurchaseOrder.created_at,
            )
            .join(Supplier, Supplier.id == PurchaseOrder.supplier_id)
            .where(
                PurchaseOrder.organisation_id == org_id,
                *_within_dates(PurchaseOrder.created_at, start_at, end_at),
            )
            .order_by(PurchaseOrder.id.desc())
        ).all()
        headers = ["PO Number", "Supplier", "Status", "Total Cost (INR)", "Created At"]
        table = [
            [r.po_number, r.supplier_name, r.status, format_minor_to_decimal_str(r.total_cost_minor), r.created_at.isoformat()]
            for r in rows
        ]
    else:
        raise ValueError(f"Unsupported report type: {report_type}")

    records = [dict(zip(headers, row)) for row in table]
    return headers, table, records


def export_report_csv(
    db: Session,
    org_id: int,
    report_type: str,
    *,
    start_at: datetime | None = None,
    end_at: datetime | None = None,
) -> str:
    headers, table, _ = generate_report(
        db, org_id, report_type, start_at=start_at, end_at=end_at
    )
    return render_csv(headers, table)
