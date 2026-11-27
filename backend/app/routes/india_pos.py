from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.core.auth_dependencies import OrgContext, require_org_roles
from app.core.database import get_db
from app.schemas.india_pos import (
    AutomationRuleCreate,
    CustomerConsentUpdate,
    InvoiceOut,
    LoyaltyAdjustRequest,
    OrgTaxProfileOut,
    OrgTaxProfileUpsert,
    PosCheckoutOut,
    PosCheckoutRequest,
    PosHeldBillCreate,
    PosHeldBillOut,
    PosShiftCloseRequest,
    PosShiftOpenRequest,
    PosShiftOut,
    RequisitionCreate,
    StockCountRequest,
    SupplierInvoiceCreate,
    SupplierPaymentRequest,
)
from app.services import crm_ops_service, india_tax_service, pos_service

router = APIRouter(prefix="/api/v1", tags=["India GST, Retail POS, CRM & Operations"])


# ---- Organisation Tax & Compliance Configuration ----


@router.get("/tax/profile", response_model=OrgTaxProfileOut)
def get_tax_profile(
    org_ctx: OrgContext = Depends(
        require_org_roles("owner", "admin", "analyst", "operator")
    ),
    db: Session = Depends(get_db),
):
    prof = india_tax_service.get_or_init_tax_profile(
        db, org_ctx.organisation.id, org_ctx.organisation.name
    )
    db.commit()
    return india_tax_service.to_tax_profile_out(prof)


@router.put("/tax/profile", response_model=OrgTaxProfileOut)
def upsert_tax_profile(
    payload: OrgTaxProfileUpsert,
    org_ctx: OrgContext = Depends(require_org_roles("owner", "admin")),
    db: Session = Depends(get_db),
):
    return india_tax_service.upsert_tax_profile(db, org_ctx, payload)


# ---- Invoices & Printable Receipts ----


@router.get("/invoices", response_model=list[InvoiceOut])
def list_invoices(
    org_ctx: OrgContext = Depends(
        require_org_roles("owner", "admin", "analyst", "operator")
    ),
    db: Session = Depends(get_db),
):
    return india_tax_service.list_invoices(db, org_ctx.organisation.id)


@router.post("/orders/{order_id}/invoice", response_model=InvoiceOut)
def generate_order_invoice(
    order_id: int,
    org_ctx: OrgContext = Depends(require_org_roles("owner", "admin", "operator")),
    db: Session = Depends(get_db),
):
    inv = india_tax_service.generate_invoice_for_order(db, org_ctx.organisation.id, order_id)
    db.commit()
    db.refresh(inv)
    return india_tax_service.to_invoice_out(inv)


@router.get("/invoices/{invoice_id}/print", response_class=HTMLResponse)
def print_invoice_html(
    invoice_id: int,
    org_ctx: OrgContext = Depends(
        require_org_roles("owner", "admin", "analyst", "operator")
    ),
    db: Session = Depends(get_db),
):
    from sqlalchemy import select
    from app.models.india_pos import Invoice
    from fastapi import HTTPException
    import html

    inv = db.scalar(
        select(Invoice).where(
            Invoice.id == invoice_id,
            Invoice.organisation_id == org_ctx.organisation.id,
        )
    )
    if inv is None:
        raise HTTPException(status_code=404, detail="Invoice not found.")
    out = india_tax_service.to_invoice_out(inv)
    items_rows = ""
    for line in out.line_items_snapshot if isinstance(out.line_items_snapshot, list) else []:
        items_rows += (
            f"<tr><td>{html.escape(str(line.get('name', '')))}</td>"
            f"<td>{html.escape(str(line.get('hsn_sac') or '-'))}</td>"
            f"<td>{html.escape(str(line.get('quantity', '')))}</td>"
            f"<td>₹{line.get('line_total_minor', 0) / 100:.2f}</td></tr>"
        )
    body = f"""<!doctype html><html><head><meta charset='utf-8'><title>{html.escape(out.invoice_number)}</title>
    <style>body{{font-family:sans-serif;max-width:680px;margin:24px auto;}}table{{width:100%;border-collapse:collapse;}}th,td{{border-bottom:1px solid #ddd;padding:6px;text-align:left;}}</style>
    </head><body>
    <h2>{html.escape(org_ctx.organisation.name)} — {html.escape(out.document_type.replace('_', ' ').upper())}</h2>
    <p><strong>Invoice No:</strong> {html.escape(out.invoice_number)} | <strong>FY:</strong> {html.escape(out.financial_year)}</p>
    <p><strong>Supplier GSTIN:</strong> {html.escape(out.supplier_gstin or 'Unregistered')} | <strong>Customer:</strong> {html.escape(out.customer_name or 'Walk-in')}</p>
    <p><strong>Place of Supply:</strong> State {html.escape(out.place_of_supply_state)} ({'IGST' if out.is_interstate else 'CGST + SGST'})</p>
    <table><thead><tr><th>Item</th><th>HSN/SAC</th><th>Qty</th><th>Line Total</th></tr></thead><tbody>{items_rows}</tbody></table>
    <p>Taxable: ₹{out.taxable_value} | CGST: ₹{out.cgst} | SGST: ₹{out.sgst} | IGST: ₹{out.igst} | <strong>Total: ₹{out.total}</strong></p>
    </body></html>"""
    return HTMLResponse(content=body)


# ---- Complete Retail POS ----


@router.get("/pos/shifts", response_model=list[PosShiftOut])
def list_pos_shifts(
    org_ctx: OrgContext = Depends(
        require_org_roles("owner", "admin", "analyst", "operator")
    ),
    db: Session = Depends(get_db),
):
    return pos_service.list_shifts(db, org_ctx.organisation.id)


@router.post("/pos/shifts/open", response_model=PosShiftOut, status_code=201)
def open_pos_shift(
    payload: PosShiftOpenRequest,
    org_ctx: OrgContext = Depends(require_org_roles("owner", "admin", "operator")),
    db: Session = Depends(get_db),
):
    return pos_service.open_shift(db, org_ctx, payload)


@router.post("/pos/shifts/{shift_id}/close", response_model=PosShiftOut)
def close_pos_shift(
    shift_id: int,
    payload: PosShiftCloseRequest,
    org_ctx: OrgContext = Depends(require_org_roles("owner", "admin", "operator")),
    db: Session = Depends(get_db),
):
    return pos_service.close_shift(db, org_ctx, shift_id, payload)


@router.get("/pos/held-bills", response_model=list[PosHeldBillOut])
def list_held_bills(
    org_ctx: OrgContext = Depends(
        require_org_roles("owner", "admin", "analyst", "operator")
    ),
    db: Session = Depends(get_db),
):
    return pos_service.list_held_bills(db, org_ctx.organisation.id)


@router.post("/pos/held-bills", response_model=PosHeldBillOut, status_code=201)
def hold_pos_bill(
    payload: PosHeldBillCreate,
    org_ctx: OrgContext = Depends(require_org_roles("owner", "admin", "operator")),
    db: Session = Depends(get_db),
):
    return pos_service.hold_bill(db, org_ctx, payload)


@router.post("/pos/checkout", response_model=PosCheckoutOut, status_code=201)
def pos_checkout(
    payload: PosCheckoutRequest,
    org_ctx: OrgContext = Depends(require_org_roles("owner", "admin", "operator")),
    db: Session = Depends(get_db),
):
    return pos_service.pos_checkout(db, org_ctx, payload)


# ---- Stock Counts, Requisitions, Supplier Invoices ----


@router.post("/retail-inventory/stock-count")
def reconcile_stock_count(
    payload: StockCountRequest,
    org_ctx: OrgContext = Depends(require_org_roles("owner", "admin", "operator")),
    db: Session = Depends(get_db),
):
    return crm_ops_service.apply_stock_count(db, org_ctx, payload)


@router.get("/requisitions")
def list_requisitions(
    org_ctx: OrgContext = Depends(
        require_org_roles("owner", "admin", "analyst", "operator")
    ),
    db: Session = Depends(get_db),
):
    return crm_ops_service.list_requisitions(db, org_ctx.organisation.id)


@router.post("/requisitions", status_code=201)
def create_requisition(
    payload: RequisitionCreate,
    org_ctx: OrgContext = Depends(require_org_roles("owner", "admin", "operator")),
    db: Session = Depends(get_db),
):
    return crm_ops_service.create_requisition(db, org_ctx, payload)


@router.post("/requisitions/{req_id}/convert")
def convert_requisition(
    req_id: int,
    org_ctx: OrgContext = Depends(require_org_roles("owner", "admin")),
    db: Session = Depends(get_db),
):
    return crm_ops_service.approve_and_convert_requisition(db, org_ctx, req_id)


@router.get("/supplier-invoices")
def list_supplier_invoices(
    org_ctx: OrgContext = Depends(
        require_org_roles("owner", "admin", "analyst", "operator")
    ),
    db: Session = Depends(get_db),
):
    return crm_ops_service.list_supplier_invoices(db, org_ctx.organisation.id)


@router.post("/supplier-invoices", status_code=201)
def create_supplier_invoice(
    payload: SupplierInvoiceCreate,
    org_ctx: OrgContext = Depends(require_org_roles("owner", "admin", "operator")),
    db: Session = Depends(get_db),
):
    return crm_ops_service.create_supplier_invoice(db, org_ctx, payload)


@router.post("/supplier-invoices/{inv_id}/pay")
def pay_supplier_invoice(
    inv_id: int,
    payload: SupplierPaymentRequest,
    org_ctx: OrgContext = Depends(require_org_roles("owner", "admin")),
    db: Session = Depends(get_db),
):
    return crm_ops_service.pay_supplier_invoice(db, org_ctx, inv_id, payload)


# ---- CRM Loyalty, Store Credit, DPDP Consent ----


@router.get("/customers/{customer_id}/profile")
def get_customer_360(
    customer_id: int,
    org_ctx: OrgContext = Depends(
        require_org_roles("owner", "admin", "analyst", "operator")
    ),
    db: Session = Depends(get_db),
):
    return crm_ops_service.get_customer_360(db, org_ctx.organisation.id, customer_id)


@router.post("/customers/{customer_id}/loyalty")
def adjust_customer_loyalty(
    customer_id: int,
    payload: LoyaltyAdjustRequest,
    org_ctx: OrgContext = Depends(require_org_roles("owner", "admin", "operator")),
    db: Session = Depends(get_db),
):
    return crm_ops_service.adjust_customer_loyalty(db, org_ctx, customer_id, payload)


@router.put("/customers/{customer_id}/consent")
def update_customer_consent(
    customer_id: int,
    payload: CustomerConsentUpdate,
    org_ctx: OrgContext = Depends(require_org_roles("owner", "admin", "operator")),
    db: Session = Depends(get_db),
):
    return crm_ops_service.update_customer_consent(db, org_ctx, customer_id, payload)


# ---- Financial P&L, Forecast Baseline, Automation, Omnichannel Adapters ----


@router.get("/sales/pnl")
def get_financial_pnl(
    org_ctx: OrgContext = Depends(require_org_roles("owner", "admin", "analyst")),
    db: Session = Depends(get_db),
):
    return crm_ops_service.get_financial_pnl_and_forecast(db, org_ctx.organisation.id)


@router.get("/integrations/readiness")
def get_integration_readiness(
    org_ctx: OrgContext = Depends(
        require_org_roles("owner", "admin", "analyst", "operator")
    ),
):
    return crm_ops_service.list_readiness_adapters()


@router.get("/automation/rules")
def list_automation_rules(
    org_ctx: OrgContext = Depends(require_org_roles("owner", "admin", "analyst")),
    db: Session = Depends(get_db),
):
    return crm_ops_service.list_automation_rules(db, org_ctx.organisation.id)


@router.post("/automation/rules", status_code=201)
def create_automation_rule(
    payload: AutomationRuleCreate,
    org_ctx: OrgContext = Depends(require_org_roles("owner", "admin")),
    db: Session = Depends(get_db),
):
    return crm_ops_service.create_automation_rule(db, org_ctx, payload)


@router.post("/automation/run")
def run_automation_rules(
    org_ctx: OrgContext = Depends(require_org_roles("owner", "admin", "operator")),
    db: Session = Depends(get_db),
):
    return crm_ops_service.run_automation_rules(db, org_ctx)
