from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.auth_dependencies import OrgContext
from app.models.india_pos import Invoice, OrgTaxProfile
from app.models.operations import OrderReturn
from app.models.retail import CommerceProduct, Customer, Order, OrderItem
from app.models.rossmann import AuditLog
from app.schemas.india_pos import InvoiceOut, OrgTaxProfileOut, OrgTaxProfileUpsert
from app.schemas.retail import format_minor_to_decimal_str


def _round_paise(value: Decimal) -> int:
    return int(value.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def compute_line_gst(
    *,
    unit_price_minor: int,
    quantity: int,
    item_discount_minor: int,
    tax_rate_bps: int,
    tax_inclusive: bool,
    is_interstate: bool,
) -> tuple[int, int, int, int, int, int]:
    """Compute exact integer paise (taxable, cgst, sgst, igst, total_tax, line_total)."""
    gross = max(0, (unit_price_minor * quantity) - item_discount_minor)
    rate = Decimal(tax_rate_bps) / Decimal(10000)

    if rate <= 0:
        return gross, 0, 0, 0, 0, gross

    if tax_inclusive:
        divisor = Decimal(1) + rate
        taxable = _round_paise(Decimal(gross) / divisor)
        total_tax = max(0, gross - taxable)
        line_total = gross
    else:
        taxable = gross
        total_tax = _round_paise(Decimal(taxable) * rate)
        line_total = taxable + total_tax

    if is_interstate:
        cgst = 0
        sgst = 0
        igst = total_tax
    else:
        cgst = total_tax // 2
        sgst = total_tax - cgst
        igst = 0

    return taxable, cgst, sgst, igst, total_tax, line_total


def get_or_init_tax_profile(db: Session, org_id: int, default_name: str = "FLASHCORE Retail") -> OrgTaxProfile:
    prof = db.scalar(
        select(OrgTaxProfile).where(OrgTaxProfile.organisation_id == org_id)
    )
    if prof is not None:
        return prof
    prof = OrgTaxProfile(
        organisation_id=org_id,
        legal_name=default_name,
        registration_type="regular",
        state_name="Maharashtra",
        state_code="27",
        invoice_prefix="INV",
        financial_year_code="2627",
        tax_inclusive_default=False,
        allow_negative_stock=False,
        dpdp_retention_days=1095,
    )
    db.add(prof)
    db.flush()
    return prof


def to_tax_profile_out(p: OrgTaxProfile) -> OrgTaxProfileOut:
    return OrgTaxProfileOut(
        id=str(p.id),
        organisation_id=p.organisation_id,
        legal_name=p.legal_name,
        gstin=p.gstin,
        registration_type=p.registration_type,
        state_name=p.state_name,
        state_code=p.state_code,
        address=p.address,
        invoice_prefix=p.invoice_prefix,
        financial_year_code=p.financial_year_code,
        tax_inclusive_default=p.tax_inclusive_default,
        allow_negative_stock=p.allow_negative_stock,
        dpdp_retention_days=p.dpdp_retention_days,
        e_invoice_provider=p.e_invoice_provider,
        e_way_provider=p.e_way_provider,
        updated_at=p.updated_at,
    )


def upsert_tax_profile(
    db: Session, org_ctx: OrgContext, payload: OrgTaxProfileUpsert
) -> OrgTaxProfileOut:
    org_id = org_ctx.organisation.id
    prof = get_or_init_tax_profile(db, org_id, org_ctx.organisation.name)
    cleaned_gstin = payload.gstin.strip().upper() if payload.gstin else None
    if cleaned_gstin and len(cleaned_gstin) != 15:
        raise HTTPException(status_code=422, detail="Indian GSTIN must be exactly 15 characters.")

    prof.legal_name = payload.legal_name.strip()
    prof.gstin = cleaned_gstin
    prof.registration_type = payload.registration_type
    prof.state_name = payload.state_name.strip()
    prof.state_code = payload.state_code.strip()
    prof.address = payload.address
    prof.invoice_prefix = payload.invoice_prefix.strip().upper()
    prof.financial_year_code = payload.financial_year_code.strip()
    prof.tax_inclusive_default = payload.tax_inclusive_default
    prof.allow_negative_stock = payload.allow_negative_stock
    prof.dpdp_retention_days = payload.dpdp_retention_days
    prof.e_invoice_provider = payload.e_invoice_provider
    prof.e_way_provider = payload.e_way_provider
    prof.updated_at = datetime.now(timezone.utc)

    db.add(
        AuditLog(
            organisation_id=org_id,
            actor_type=org_ctx.membership.role,
            actor_ref=org_ctx.user.email,
            action="org_tax_profile_updated",
            entity_name="org_tax_profiles",
            entity_id=str(prof.id),
            details={"gstin": prof.gstin, "state_code": prof.state_code, "registration_type": prof.registration_type},
        )
    )
    db.commit()
    db.refresh(prof)
    return to_tax_profile_out(prof)


def _next_invoice_number(db: Session, org_id: int, prefix: str, fy: str) -> str:
    seq = int(
        db.scalar(
            select(func.count(Invoice.id)).where(
                Invoice.organisation_id == org_id,
                Invoice.financial_year == fy,
            )
        )
        or 0
    ) + 1
    return f"{prefix}-{fy}-{seq:05d}"


def to_invoice_out(inv: Invoice) -> InvoiceOut:
    return InvoiceOut(
        id=str(inv.id),
        organisation_id=inv.organisation_id,
        invoice_number=inv.invoice_number,
        document_type=inv.document_type,
        financial_year=inv.financial_year,
        order_id=str(inv.order_id) if inv.order_id else None,
        return_id=str(inv.return_id) if inv.return_id else None,
        customer_id=inv.customer_id,
        customer_name=inv.customer_name,
        customer_gstin=inv.customer_gstin,
        supplier_gstin=inv.supplier_gstin,
        place_of_supply_state=inv.place_of_supply_state,
        is_interstate=inv.is_interstate,
        taxable_value_minor=inv.taxable_value_minor,
        taxable_value=format_minor_to_decimal_str(inv.taxable_value_minor),
        discount_minor=inv.discount_minor,
        discount=format_minor_to_decimal_str(inv.discount_minor),
        cgst_minor=inv.cgst_minor,
        cgst=format_minor_to_decimal_str(inv.cgst_minor),
        sgst_minor=inv.sgst_minor,
        sgst=format_minor_to_decimal_str(inv.sgst_minor),
        igst_minor=inv.igst_minor,
        igst=format_minor_to_decimal_str(inv.igst_minor),
        total_tax_minor=inv.total_tax_minor,
        total_tax=format_minor_to_decimal_str(inv.total_tax_minor),
        total_minor=inv.total_minor,
        total=format_minor_to_decimal_str(inv.total_minor),
        status=inv.status,
        irn_status=inv.irn_status,
        line_items_snapshot=inv.line_items_snapshot,
        issued_at=inv.issued_at,
    )


def generate_invoice_for_order(
    db: Session,
    org_id: int,
    order_id: int,
    *,
    document_type: str = "tax_invoice",
) -> Invoice:
    existing = db.scalar(
        select(Invoice).where(
            Invoice.organisation_id == org_id,
            Invoice.order_id == order_id,
            Invoice.document_type == document_type,
        )
    )
    if existing is not None:
        return existing

    order = db.scalar(
        select(Order).where(Order.id == order_id, Order.organisation_id == org_id)
    )
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found.")

    prof = get_or_init_tax_profile(db, org_id)
    cust = db.get(Customer, order.customer_id) if order.customer_id else None
    pos_state = (
        order.place_of_supply_state
        or (cust.state_code if cust and cust.state_code else prof.state_code)
    )
    is_interstate = pos_state != prof.state_code

    items = list(
        db.scalars(
            select(OrderItem).where(
                OrderItem.order_id == order.id,
                OrderItem.organisation_id == org_id,
            )
        ).all()
    )
    prods = {
        p.id: p
        for p in db.scalars(
            select(CommerceProduct).where(
                CommerceProduct.id.in_([i.product_id for i in items])
            )
        ).all()
    } if items else {}

    doc_type = (
        "bill_of_supply"
        if prof.registration_type in ("composition", "unregistered")
        else document_type
    )
    prefix = "BOS" if doc_type == "bill_of_supply" else prof.invoice_prefix
    inv_num = _next_invoice_number(db, org_id, prefix, prof.financial_year_code)

    cgst = order.cgst_minor
    sgst = order.sgst_minor
    igst = order.igst_minor
    if cgst + sgst + igst == 0 and order.tax_minor > 0:
        if is_interstate:
            igst = order.tax_minor
        else:
            cgst = order.tax_minor // 2
            sgst = order.tax_minor - cgst

    snapshot = [
        {
            "sku": it.sku_snapshot,
            "name": it.name_snapshot,
            "hsn_sac": prods[it.product_id].hsn_sac_code if it.product_id in prods else None,
            "quantity": it.quantity,
            "unit_price_minor": it.unit_price_minor,
            "tax_rate_bps": it.tax_rate_bps,
            "tax_minor": it.tax_minor,
            "line_total_minor": it.line_total_minor,
        }
        for it in items
    ]

    cust_name = cust.name if cust else (
        order.customer_snapshot.get("name")
        if isinstance(order.customer_snapshot, dict)
        else "Walk-in Customer"
    )
    inv = Invoice(
        organisation_id=org_id,
        invoice_number=inv_num,
        document_type=doc_type,
        financial_year=prof.financial_year_code,
        order_id=order.id,
        customer_id=order.customer_id,
        customer_name=cust_name,
        customer_gstin=cust.gstin if cust else None,
        supplier_gstin=prof.gstin,
        place_of_supply_state=pos_state,
        is_interstate=is_interstate,
        taxable_value_minor=max(0, order.subtotal_minor - order.discount_minor),
        discount_minor=order.discount_minor,
        cgst_minor=cgst,
        sgst_minor=sgst,
        igst_minor=igst,
        total_tax_minor=cgst + sgst + igst,
        total_minor=order.total_minor,
        status="ISSUED",
        irn_status="ADAPTER_READY" if prof.e_invoice_provider else "NOT_APPLICABLE",
        line_items_snapshot=snapshot,
    )
    db.add(inv)
    db.flush()
    return inv


def generate_credit_note_for_return(db: Session, org_id: int, return_id: int) -> Invoice:
    existing = db.scalar(
        select(Invoice).where(
            Invoice.organisation_id == org_id,
            Invoice.return_id == return_id,
            Invoice.document_type == "credit_note",
        )
    )
    if existing is not None:
        return existing

    ret = db.scalar(
        select(OrderReturn).where(
            OrderReturn.id == return_id,
            OrderReturn.organisation_id == org_id,
        )
    )
    if ret is None:
        raise HTTPException(status_code=404, detail="Return not found.")

    orig_inv = db.scalar(
        select(Invoice).where(
            Invoice.organisation_id == org_id,
            Invoice.order_id == ret.order_id,
        )
    )
    prof = get_or_init_tax_profile(db, org_id)
    cn_num = _next_invoice_number(db, org_id, "CN", prof.financial_year_code)

    total = ret.refund_amount_minor
    tax = (orig_inv.total_tax_minor * total // orig_inv.total_minor) if (orig_inv and orig_inv.total_minor > 0) else 0
    taxable = max(0, total - tax)
    is_inter = orig_inv.is_interstate if orig_inv else False
    igst = tax if is_inter else 0
    cgst = (tax // 2) if not is_inter else 0
    sgst = (tax - cgst) if not is_inter else 0

    cn = Invoice(
        organisation_id=org_id,
        invoice_number=cn_num,
        document_type="credit_note",
        financial_year=prof.financial_year_code,
        order_id=ret.order_id,
        return_id=ret.id,
        customer_id=ret.customer_id,
        customer_name=orig_inv.customer_name if orig_inv else None,
        customer_gstin=orig_inv.customer_gstin if orig_inv else None,
        supplier_gstin=prof.gstin,
        place_of_supply_state=orig_inv.place_of_supply_state if orig_inv else prof.state_code,
        is_interstate=is_inter,
        taxable_value_minor=taxable,
        discount_minor=0,
        cgst_minor=cgst,
        sgst_minor=sgst,
        igst_minor=igst,
        total_tax_minor=tax,
        total_minor=total,
        status="ISSUED",
        irn_status="NOT_APPLICABLE",
        line_items_snapshot=[{"return_number": ret.return_number, "reason": ret.reason, "amount_minor": total}],
    )
    db.add(cn)
    db.flush()
    return cn


def list_invoices(db: Session, org_id: int) -> list[InvoiceOut]:
    rows = db.scalars(
        select(Invoice)
        .where(Invoice.organisation_id == org_id)
        .order_by(Invoice.id.desc())
    ).all()
    return [to_invoice_out(r) for r in rows]
