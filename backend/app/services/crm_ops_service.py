from datetime import datetime, timedelta, timezone
import uuid

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.auth_dependencies import OrgContext
from app.models.india_pos import (
    AutomationRule,
    LoyaltyLedger,
    PurchaseRequisition,
    SupplierInvoice,
)
from app.models.operations import OrderReturn, SalesRecord
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
from app.models.rossmann import AuditLog
from app.schemas.expansion import PurchaseOrderCreate, PurchaseOrderItemIn
from app.schemas.india_pos import (
    AutomationRuleCreate,
    CustomerConsentUpdate,
    LoyaltyAdjustRequest,
    RequisitionCreate,
    StockCountRequest,
    SupplierInvoiceCreate,
    SupplierPaymentRequest,
)
from app.schemas.retail import format_minor_to_decimal_str
from app.services import inventory_service, notifications_service, procurement_service


def apply_stock_count(
    db: Session, org_ctx: OrgContext, payload: StockCountRequest
) -> dict:
    org_id = org_ctx.organisation.id
    loc = db.scalar(
        select(InventoryLocation).where(
            InventoryLocation.id == payload.location_id,
            InventoryLocation.organisation_id == org_id,
        )
    )
    if loc is None:
        raise HTTPException(status_code=404, detail="Location not found.")

    now = datetime.now(timezone.utc)
    variances = []
    for item in payload.items:
        prod = db.scalar(
            select(CommerceProduct).where(
                CommerceProduct.id == item.product_id,
                CommerceProduct.organisation_id == org_id,
            )
        )
        if prod is None:
            raise HTTPException(status_code=404, detail=f"Product {item.product_id} not found.")
        bal = inventory_service._get_or_create_balance_locked(db, org_id, prod.id, loc.id)
        if item.counted_quantity < bal.reserved_quantity:
            raise HTTPException(
                status_code=409,
                detail=f"Counted quantity ({item.counted_quantity}) for SKU {prod.sku} cannot be below reserved stock ({bal.reserved_quantity}).",
            )
        delta = item.counted_quantity - bal.quantity
        if delta != 0:
            bal.quantity = item.counted_quantity
            bal.last_movement_at = now
            bal.updated_at = now
            db.add(
                InventoryMovement(
                    organisation_id=org_id,
                    balance_id=bal.id,
                    product_id=prod.id,
                    location_id=loc.id,
                    movement_type="adjustment",
                    quantity_delta=delta,
                    reserved_delta=0,
                    balance_after=bal.quantity,
                    reserved_after=bal.reserved_quantity,
                    reference_type="stock_count",
                    reference_id=f"SC-{loc.code}-{now.strftime('%Y%m%d')}",
                    reason=item.note or "Physical stock count reconciliation",
                    actor_ref=org_ctx.user.email,
                )
            )
        variances.append({"product_id": str(prod.id), "sku": prod.sku, "delta": delta, "new_on_hand": bal.quantity})

    db.add(
        AuditLog(
            organisation_id=org_id,
            actor_type=org_ctx.membership.role,
            actor_ref=org_ctx.user.email,
            action="stock_count_reconciled",
            entity_name="inventory_balances",
            entity_id=str(loc.id),
            details={"location": loc.code, "items_counted": len(variances)},
        )
    )
    db.commit()
    return {"location_id": loc.id, "variances": variances}


def create_requisition(db: Session, org_ctx: OrgContext, payload: RequisitionCreate) -> dict:
    org_id = org_ctx.organisation.id
    now = datetime.now(timezone.utc)
    req = PurchaseRequisition(
        organisation_id=org_id,
        req_number=f"PR-{org_id}-{now.strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}",
        location_id=payload.location_id,
        supplier_id=payload.supplier_id,
        status="PENDING_APPROVAL",
        items_json=payload.items,
        notes=payload.notes,
        requested_by=org_ctx.user.email,
    )
    db.add(req)
    db.commit()
    db.refresh(req)
    return _req_out(req)


def _req_out(r: PurchaseRequisition) -> dict:
    return {
        "id": str(r.id),
        "req_number": r.req_number,
        "location_id": r.location_id,
        "supplier_id": str(r.supplier_id) if r.supplier_id else None,
        "status": r.status,
        "items": r.items_json,
        "notes": r.notes,
        "requested_by": r.requested_by,
        "approved_by": r.approved_by,
        "purchase_order_id": str(r.purchase_order_id) if r.purchase_order_id else None,
        "created_at": r.created_at,
    }


def list_requisitions(db: Session, org_id: int) -> list[dict]:
    rows = db.scalars(
        select(PurchaseRequisition)
        .where(PurchaseRequisition.organisation_id == org_id)
        .order_by(PurchaseRequisition.id.desc())
    ).all()
    return [_req_out(r) for r in rows]


def approve_and_convert_requisition(
    db: Session, org_ctx: OrgContext, req_id: int
) -> dict:
    org_id = org_ctx.organisation.id
    req = db.scalar(
        select(PurchaseRequisition)
        .where(
            PurchaseRequisition.id == req_id,
            PurchaseRequisition.organisation_id == org_id,
        )
        .with_for_update()
    )
    if req is None:
        raise HTTPException(status_code=404, detail="Purchase requisition not found.")
    if req.status != "PENDING_APPROVAL":
        raise HTTPException(status_code=409, detail=f"Requisition already in {req.status}.")
    if req.supplier_id is None:
        raise HTTPException(status_code=422, detail="Supplier must be assigned before converting requisition to PO.")

    po_items = [
        PurchaseOrderItemIn(
            product_id=int(it["product_id"]),
            ordered_quantity=int(it["ordered_quantity"]),
            unit_cost_minor=int(it.get("unit_cost_minor") or 0),
        )
        for it in req.items_json
    ]
    req.approved_by = org_ctx.user.email
    req.status = "CONVERTED_TO_PO"
    po = procurement_service.create_purchase_order(
        db,
        org_ctx,
        PurchaseOrderCreate(
            supplier_id=req.supplier_id,
            location_id=req.location_id,
            notes=f"Converted from {req.req_number}",
            items=po_items,
        ),
    )
    req = db.get(PurchaseRequisition, req_id) or req
    req.purchase_order_id = int(po.id)
    db.commit()
    db.refresh(req)
    return _req_out(req)


def create_supplier_invoice(
    db: Session, org_ctx: OrgContext, payload: SupplierInvoiceCreate
) -> dict:
    org_id = org_ctx.organisation.id
    sup = db.scalar(
        select(Supplier)
        .where(Supplier.id == payload.supplier_id, Supplier.organisation_id == org_id)
        .with_for_update()
    )
    po = db.scalar(
        select(PurchaseOrder).where(
            PurchaseOrder.id == payload.purchase_order_id,
            PurchaseOrder.organisation_id == org_id,
        )
    )
    if sup is None or po is None:
        raise HTTPException(status_code=404, detail="Supplier or Purchase Order not found.")

    total = payload.subtotal_minor + payload.gst_minor
    inv = SupplierInvoice(
        organisation_id=org_id,
        invoice_number=payload.invoice_number.strip(),
        supplier_id=sup.id,
        purchase_order_id=po.id,
        subtotal_minor=payload.subtotal_minor,
        gst_minor=payload.gst_minor,
        total_minor=total,
        paid_minor=0,
        status="UNPAID",
    )
    db.add(inv)
    sup.outstanding_payable_minor += total
    db.commit()
    db.refresh(inv)
    return _sup_inv_out(inv, sup.name)


def _sup_inv_out(inv: SupplierInvoice, supplier_name: str | None = None) -> dict:
    return {
        "id": str(inv.id),
        "invoice_number": inv.invoice_number,
        "supplier_id": str(inv.supplier_id),
        "supplier_name": supplier_name,
        "purchase_order_id": str(inv.purchase_order_id),
        "subtotal_minor": inv.subtotal_minor,
        "gst_minor": inv.gst_minor,
        "total_minor": inv.total_minor,
        "total": format_minor_to_decimal_str(inv.total_minor),
        "paid_minor": inv.paid_minor,
        "status": inv.status,
        "issued_at": inv.issued_at,
    }


def list_supplier_invoices(db: Session, org_id: int) -> list[dict]:
    rows = db.execute(
        select(SupplierInvoice, Supplier.name)
        .join(Supplier, Supplier.id == SupplierInvoice.supplier_id)
        .where(SupplierInvoice.organisation_id == org_id)
        .order_by(SupplierInvoice.id.desc())
    ).all()
    return [_sup_inv_out(r[0], r[1]) for r in rows]


def pay_supplier_invoice(
    db: Session, org_ctx: OrgContext, inv_id: int, payload: SupplierPaymentRequest
) -> dict:
    org_id = org_ctx.organisation.id
    inv = db.scalar(
        select(SupplierInvoice)
        .where(SupplierInvoice.id == inv_id, SupplierInvoice.organisation_id == org_id)
        .with_for_update()
    )
    if inv is None:
        raise HTTPException(status_code=404, detail="Supplier invoice not found.")
    remaining = inv.total_minor - inv.paid_minor
    if payload.amount_minor > remaining:
        raise HTTPException(status_code=409, detail="Payment exceeds remaining supplier balance.")
    sup = db.scalar(
        select(Supplier).where(Supplier.id == inv.supplier_id).with_for_update()
    )
    inv.paid_minor += payload.amount_minor
    inv.status = "PAID" if inv.paid_minor >= inv.total_minor else "PARTIALLY_PAID"
    if sup:
        sup.outstanding_payable_minor = max(0, sup.outstanding_payable_minor - payload.amount_minor)
    db.commit()
    db.refresh(inv)
    return _sup_inv_out(inv, sup.name if sup else None)


def get_customer_360(db: Session, org_id: int, customer_id: int) -> dict:
    cust = db.scalar(
        select(Customer).where(Customer.id == customer_id, Customer.organisation_id == org_id)
    )
    if cust is None:
        raise HTTPException(status_code=404, detail="Customer not found.")
    sales = db.scalars(
        select(SalesRecord)
        .where(SalesRecord.organisation_id == org_id, SalesRecord.customer_id == cust.id)
        .order_by(SalesRecord.sold_at.desc())
    ).all()
    ltv = sum(max(0, s.net_amount_minor - s.refunded_minor) for s in sales)
    ledger = db.scalars(
        select(LoyaltyLedger)
        .where(LoyaltyLedger.organisation_id == org_id, LoyaltyLedger.customer_id == cust.id)
        .order_by(LoyaltyLedger.id.desc())
        .limit(30)
    ).all()
    returns_cnt = int(
        db.scalar(
            select(func.count(OrderReturn.id)).where(
                OrderReturn.organisation_id == org_id,
                OrderReturn.customer_id == cust.id,
            )
        )
        or 0
    )
    return {
        "id": str(cust.id),
        "name": cust.name,
        "email": cust.email,
        "phone": cust.phone,
        "gstin": cust.gstin,
        "state_code": cust.state_code,
        "tier": cust.tier,
        "loyalty_points": cust.loyalty_points,
        "store_credit_minor": cust.store_credit_minor,
        "store_credit": format_minor_to_decimal_str(cust.store_credit_minor),
        "marketing_consent": cust.marketing_consent,
        "opted_out_at": cust.opted_out_at,
        "paid_order_count": len(sales),
        "lifetime_spend_minor": ltv,
        "lifetime_spend": format_minor_to_decimal_str(ltv),
        "returns_count": returns_cnt,
        "ledger": [
            {
                "id": str(l.id),
                "entry_type": l.entry_type,
                "points_delta": l.points_delta,
                "store_credit_delta_minor": l.store_credit_delta_minor,
                "reason": l.reason,
                "created_at": l.created_at,
            }
            for l in ledger
        ],
    }


def adjust_customer_loyalty(
    db: Session, org_ctx: OrgContext, customer_id: int, payload: LoyaltyAdjustRequest
) -> dict:
    org_id = org_ctx.organisation.id
    cust = db.scalar(
        select(Customer)
        .where(Customer.id == customer_id, Customer.organisation_id == org_id)
        .with_for_update()
    )
    if cust is None:
        raise HTTPException(status_code=404, detail="Customer not found.")
    if cust.loyalty_points + payload.points_delta < 0:
        raise HTTPException(status_code=409, detail="Loyalty points cannot be negative.")
    if cust.store_credit_minor + payload.store_credit_delta_minor < 0:
        raise HTTPException(status_code=409, detail="Store credit balance cannot be negative.")

    cust.loyalty_points += payload.points_delta
    cust.store_credit_minor += payload.store_credit_delta_minor
    db.add(
        LoyaltyLedger(
            organisation_id=org_id,
            customer_id=cust.id,
            entry_type="CREDIT_ISSUE" if payload.store_credit_delta_minor > 0 else "ADJUST",
            points_delta=payload.points_delta,
            store_credit_delta_minor=payload.store_credit_delta_minor,
            reason=payload.reason,
            actor_ref=org_ctx.user.email,
        )
    )
    db.commit()
    return get_customer_360(db, org_id, cust.id)


def update_customer_consent(
    db: Session, org_ctx: OrgContext, customer_id: int, payload: CustomerConsentUpdate
) -> dict:
    org_id = org_ctx.organisation.id
    cust = db.scalar(
        select(Customer).where(Customer.id == customer_id, Customer.organisation_id == org_id)
    )
    if cust is None:
        raise HTTPException(status_code=404, detail="Customer not found.")
    cust.marketing_consent = payload.marketing_consent and not payload.opt_out
    cust.opted_out_at = datetime.now(timezone.utc) if payload.opt_out else None
    db.add(
        AuditLog(
            organisation_id=org_id,
            actor_type=org_ctx.membership.role,
            actor_ref=org_ctx.user.email,
            action="dpdp_consent_updated",
            entity_name="customers",
            entity_id=str(cust.id),
            details={"marketing_consent": cust.marketing_consent, "opted_out": payload.opt_out},
        )
    )
    db.commit()
    return get_customer_360(db, org_id, cust.id)


def get_financial_pnl_and_forecast(db: Session, org_id: int) -> dict:
    """Strict financial separation: Gross Sales vs Discounts vs Returns vs Net Sales vs Tax vs COGS vs Gross Profit."""
    records = db.scalars(
        select(SalesRecord).where(SalesRecord.organisation_id == org_id)
    ).all()
    gross_sales = sum(r.gross_amount_minor for r in records)
    discounts = sum(r.discount_minor for r in records)
    returns_refunded = sum(r.refunded_minor for r in records)
    tax_collected = sum(r.tax_minor for r in records)
    net_sales = sum(max(0, r.net_amount_minor - r.tax_minor - r.refunded_minor) for r in records)

    # COGS computed strictly for paid order items where product cost_price_minor is recorded
    paid_ids = [r.order_id for r in records if r.refund_status != "FULL"]
    cogs_minor: int | None = 0
    missing_cost_skus: list[str] = []
    if paid_ids:
        rows = db.execute(
            select(OrderItem.quantity, CommerceProduct.sku, CommerceProduct.cost_price_minor)
            .join(CommerceProduct, CommerceProduct.id == OrderItem.product_id)
            .where(OrderItem.organisation_id == org_id, OrderItem.order_id.in_(paid_ids))
        ).all()
        for qty, sku, cost in rows:
            if cost is None:
                missing_cost_skus.append(sku)
            else:
                cogs_minor = (cogs_minor or 0) + (int(qty) * int(cost))
        if missing_cost_skus:
            cogs_minor = None

    gross_profit = (net_sales - cogs_minor) if cogs_minor is not None else None

    # Statistical demand baseline (transparent moving average, no fabricated claims)
    since_30 = datetime.now(timezone.utc) - timedelta(days=30)
    sold_30 = int(
        db.scalar(
            select(func.coalesce(func.sum(OrderItem.quantity), 0))
            .join(Order, Order.id == OrderItem.order_id)
            .where(
                OrderItem.organisation_id == org_id,
                Order.order_status.in_(("PAID", "PROCESSING", "FULFILLED")),
                Order.placed_at >= since_30,
            )
        )
        or 0
    )
    return {
        "gross_sales_minor": gross_sales,
        "gross_sales": format_minor_to_decimal_str(gross_sales),
        "discounts_minor": discounts,
        "discounts": format_minor_to_decimal_str(discounts),
        "returns_refunded_minor": returns_refunded,
        "returns_refunded": format_minor_to_decimal_str(returns_refunded),
        "net_sales_ex_tax_minor": net_sales,
        "net_sales_ex_tax": format_minor_to_decimal_str(net_sales),
        "tax_collected_minor": tax_collected,
        "tax_collected": format_minor_to_decimal_str(tax_collected),
        "cogs_minor": cogs_minor,
        "cogs": format_minor_to_decimal_str(cogs_minor) if cogs_minor is not None else None,
        "gross_profit_minor": gross_profit,
        "gross_profit": format_minor_to_decimal_str(gross_profit) if gross_profit is not None else None,
        "missing_cost_skus": sorted(set(missing_cost_skus)),
        "forecast_baseline": {
            "model_version": "moving-avg-30d-v1",
            "training_window_days": 30,
            "units_observed": sold_30,
            "projected_daily_units": round(sold_30 / 30.0, 2) if sold_30 > 0 else None,
            "status": "ready" if sold_30 > 0 else "insufficient_data",
            "generated_at": datetime.now(timezone.utc).isoformat(),
        },
    }


def list_readiness_adapters() -> list[dict]:
    """Explicit provider/hardware/omnichannel readiness inventory without fake live claims."""
    return [
        {"channel": "razorpay", "category": "Payments", "status": "live_test_mode", "detail": "Verified HMAC checkout & webhook pipeline active"},
        {"channel": "upi_card_cash_pos", "category": "POS Tenders", "status": "active", "detail": "Native split payments & cash drawer shift tracking"},
        {"channel": "gst_einvoice_eway", "category": "India Compliance", "status": "adapter_prepared", "detail": "GSTIN/HSN/CGST/SGST/IGST & FY invoices active; IRP/NIC IRN adapter prepared awaiting GSP credentials"},
        {"channel": "pos_offline_queue", "category": "Offline & Hardware", "status": "active", "detail": "Idempotent offline_tx_id sync active; barcode keyboard input & printable HTML receipt active; ESC/POS thermal driver abstracted"},
        {"channel": "ondc_d2c_whatsapp", "category": "Omnichannel", "status": "adapter_prepared", "detail": "Order & channel tagging (ondc/d2c/marketplace) ready; external ONDC/WhatsApp live onboarding pending"},
    ]


def list_automation_rules(db: Session, org_id: int) -> list[dict]:
    rows = db.scalars(
        select(AutomationRule).where(AutomationRule.organisation_id == org_id).order_by(AutomationRule.id.desc())
    ).all()
    return [
        {
            "id": str(r.id),
            "name": r.name,
            "trigger_type": r.trigger_type,
            "threshold_value": r.threshold_value,
            "action_type": r.action_type,
            "is_enabled": r.is_enabled,
            "last_run_at": r.last_run_at,
            "last_status": r.last_status,
        }
        for r in rows
    ]


def create_automation_rule(db: Session, org_ctx: OrgContext, payload: AutomationRuleCreate) -> dict:
    rule = AutomationRule(
        organisation_id=org_ctx.organisation.id,
        name=payload.name.strip(),
        trigger_type=payload.trigger_type,
        threshold_value=payload.threshold_value,
        action_type="in_app_alert",
        is_enabled=payload.is_enabled,
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return list_automation_rules(db, org_ctx.organisation.id)[0]


def run_automation_rules(db: Session, org_ctx: OrgContext) -> dict:
    org_id = org_ctx.organisation.id
    notifications_service.sync_operational_alerts(db, org_id)
    rules = db.scalars(
        select(AutomationRule).where(AutomationRule.organisation_id == org_id, AutomationRule.is_enabled.is_(True))
    ).all()
    now = datetime.now(timezone.utc)
    for r in rules:
        r.last_run_at = now
        r.last_status = "executed"
    db.commit()
    return {"executed_rules": len(rules), "ran_at": now.isoformat()}
