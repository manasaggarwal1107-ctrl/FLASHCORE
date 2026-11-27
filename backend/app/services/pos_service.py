from datetime import datetime, timezone
import uuid

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.auth_dependencies import OrgContext
from app.models.campaigns import PromotionRedemption, SurgeCampaign, SurgeCampaignProduct
from app.models.india_pos import (
    LoyaltyLedger,
    OrderPaymentSplit,
    PosHeldBill,
    PosShift,
)
from app.models.retail import (
    CommerceProduct,
    Customer,
    InventoryLocation,
    InventoryMovement,
    Order,
    OrderEvent,
    OrderItem,
)
from app.models.rossmann import AuditLog
from app.schemas.india_pos import (
    PosCheckoutOut,
    PosCheckoutRequest,
    PosHeldBillCreate,
    PosHeldBillOut,
    PosShiftCloseRequest,
    PosShiftOpenRequest,
    PosShiftOut,
)
from app.schemas.retail import format_minor_to_decimal_str
from app.services import (
    campaign_service,
    india_tax_service,
    inventory_service,
    sales_service,
)


def _to_shift_out(db: Session, s: PosShift) -> PosShiftOut:
    loc = db.get(InventoryLocation, s.location_id)
    return PosShiftOut(
        id=str(s.id),
        organisation_id=s.organisation_id,
        location_id=s.location_id,
        location_name=loc.name if loc else f"Location #{s.location_id}",
        cashier_email=s.cashier_email,
        status=s.status,
        opening_cash_minor=s.opening_cash_minor,
        opening_cash=format_minor_to_decimal_str(s.opening_cash_minor),
        cash_sales_minor=s.cash_sales_minor,
        cash_sales=format_minor_to_decimal_str(s.cash_sales_minor),
        upi_sales_minor=s.upi_sales_minor,
        upi_sales=format_minor_to_decimal_str(s.upi_sales_minor),
        card_sales_minor=s.card_sales_minor,
        card_sales=format_minor_to_decimal_str(s.card_sales_minor),
        bank_sales_minor=s.bank_sales_minor,
        bank_sales=format_minor_to_decimal_str(s.bank_sales_minor),
        expected_cash_minor=s.expected_cash_minor,
        expected_cash=format_minor_to_decimal_str(s.expected_cash_minor),
        counted_cash_minor=s.counted_cash_minor,
        counted_cash=format_minor_to_decimal_str(s.counted_cash_minor) if s.counted_cash_minor is not None else None,
        variance_minor=s.variance_minor,
        variance=format_minor_to_decimal_str(s.variance_minor) if s.variance_minor is not None else None,
        opened_at=s.opened_at,
        closed_at=s.closed_at,
    )


def open_shift(db: Session, org_ctx: OrgContext, payload: PosShiftOpenRequest) -> PosShiftOut:
    org_id = org_ctx.organisation.id
    loc = db.scalar(
        select(InventoryLocation).where(
            InventoryLocation.id == payload.location_id,
            InventoryLocation.organisation_id == org_id,
        )
    )
    if loc is None:
        raise HTTPException(status_code=404, detail="Store/Warehouse location not found.")

    existing_open = db.scalar(
        select(PosShift).where(
            PosShift.organisation_id == org_id,
            PosShift.cashier_user_id == org_ctx.user.id,
            PosShift.status == "OPEN",
        )
    )
    if existing_open is not None:
        return _to_shift_out(db, existing_open)

    shift = PosShift(
        organisation_id=org_id,
        location_id=loc.id,
        cashier_user_id=org_ctx.user.id,
        cashier_email=org_ctx.user.email,
        status="OPEN",
        opening_cash_minor=payload.opening_cash_minor,
        expected_cash_minor=payload.opening_cash_minor,
        notes=payload.notes,
    )
    db.add(shift)
    db.flush()
    db.add(
        AuditLog(
            organisation_id=org_id,
            actor_type=org_ctx.membership.role,
            actor_ref=org_ctx.user.email,
            action="pos_shift_opened",
            entity_name="pos_shifts",
            entity_id=str(shift.id),
            details={"location_id": loc.id, "opening_cash_minor": payload.opening_cash_minor},
        )
    )
    db.commit()
    db.refresh(shift)
    return _to_shift_out(db, shift)


def close_shift(
    db: Session, org_ctx: OrgContext, shift_id: int, payload: PosShiftCloseRequest
) -> PosShiftOut:
    org_id = org_ctx.organisation.id
    shift = db.scalar(
        select(PosShift)
        .where(PosShift.id == shift_id, PosShift.organisation_id == org_id)
        .with_for_update()
    )
    if shift is None:
        raise HTTPException(status_code=404, detail="POS shift not found.")
    if shift.status == "CLOSED":
        return _to_shift_out(db, shift)

    now = datetime.now(timezone.utc)
    shift.counted_cash_minor = payload.counted_cash_minor
    shift.variance_minor = payload.counted_cash_minor - shift.expected_cash_minor
    shift.status = "CLOSED"
    shift.closed_at = now
    if payload.notes:
        shift.notes = payload.notes

    db.add(
        AuditLog(
            organisation_id=org_id,
            actor_type=org_ctx.membership.role,
            actor_ref=org_ctx.user.email,
            action="pos_shift_closed",
            entity_name="pos_shifts",
            entity_id=str(shift.id),
            details={
                "expected_cash_minor": shift.expected_cash_minor,
                "counted_cash_minor": shift.counted_cash_minor,
                "variance_minor": shift.variance_minor,
            },
        )
    )
    db.commit()
    db.refresh(shift)
    return _to_shift_out(db, shift)


def list_shifts(db: Session, org_id: int) -> list[PosShiftOut]:
    rows = db.scalars(
        select(PosShift)
        .where(PosShift.organisation_id == org_id)
        .order_by(PosShift.id.desc())
        .limit(25)
    ).all()
    return [_to_shift_out(db, r) for r in rows]


def hold_bill(db: Session, org_ctx: OrgContext, payload: PosHeldBillCreate) -> PosHeldBillOut:
    org_id = org_ctx.organisation.id
    bill = PosHeldBill(
        organisation_id=org_id,
        location_id=payload.location_id,
        cashier_email=org_ctx.user.email,
        label=payload.label.strip(),
        customer_id=payload.customer_id,
        coupon_code=payload.coupon_code.strip().upper() if payload.coupon_code else None,
        discount_minor=payload.discount_minor,
        items_json=[i.model_dump() for i in payload.items],
        status="HELD",
    )
    db.add(bill)
    db.commit()
    db.refresh(bill)
    return PosHeldBillOut(
        id=str(bill.id),
        location_id=bill.location_id,
        cashier_email=bill.cashier_email,
        label=bill.label,
        customer_id=bill.customer_id,
        coupon_code=bill.coupon_code,
        discount_minor=bill.discount_minor,
        items=bill.items_json,
        status=bill.status,
        created_at=bill.created_at,
    )


def list_held_bills(db: Session, org_id: int) -> list[PosHeldBillOut]:
    rows = db.scalars(
        select(PosHeldBill)
        .where(PosHeldBill.organisation_id == org_id, PosHeldBill.status == "HELD")
        .order_by(PosHeldBill.id.desc())
    ).all()
    return [
        PosHeldBillOut(
            id=str(b.id),
            location_id=b.location_id,
            cashier_email=b.cashier_email,
            label=b.label,
            customer_id=b.customer_id,
            coupon_code=b.coupon_code,
            discount_minor=b.discount_minor,
            items=b.items_json,
            status=b.status,
            created_at=b.created_at,
        )
        for b in rows
    ]


def pos_checkout(db: Session, org_ctx: OrgContext, payload: PosCheckoutRequest) -> PosCheckoutOut:
    org_id = org_ctx.organisation.id
    now = datetime.now(timezone.utc)

    # Idempotent replay check for offline POS queue synchronization
    if payload.offline_tx_id:
        existing_ord = db.scalar(
            select(Order).where(
                Order.organisation_id == org_id,
                Order.offline_tx_id == payload.offline_tx_id.strip(),
            )
        )
        if existing_ord is not None:
            inv = india_tax_service.generate_invoice_for_order(db, org_id, existing_ord.id)
            splits = db.scalars(
                select(OrderPaymentSplit).where(OrderPaymentSplit.order_id == existing_ord.id)
            ).all()
            return PosCheckoutOut(
                order_id=str(existing_ord.id),
                order_number=existing_ord.order_number,
                order_status=existing_ord.order_status,
                payment_status=existing_ord.payment_status,
                invoice=india_tax_service.to_invoice_out(inv),
                subtotal_minor=existing_ord.subtotal_minor,
                discount_minor=existing_ord.discount_minor,
                cgst_minor=existing_ord.cgst_minor,
                sgst_minor=existing_ord.sgst_minor,
                igst_minor=existing_ord.igst_minor,
                total_minor=existing_ord.total_minor,
                total=format_minor_to_decimal_str(existing_ord.total_minor),
                payments=[
                    {"method": sp.method, "amount_minor": sp.amount_minor, "reference_utr": sp.reference_utr, "verified": sp.verified}
                    for sp in splits
                ],
                offline_replayed=True,
            )

    location = db.scalar(
        select(InventoryLocation).where(
            InventoryLocation.id == payload.location_id,
            InventoryLocation.organisation_id == org_id,
            InventoryLocation.is_active.is_(True),
        )
    )
    if location is None:
        raise HTTPException(status_code=404, detail="Active POS location not found.")

    tax_profile = india_tax_service.get_or_init_tax_profile(db, org_id, org_ctx.organisation.name)
    customer = None
    cust_snap = None
    if payload.customer_id is not None:
        customer = db.scalar(
            select(Customer)
            .where(Customer.id == payload.customer_id, Customer.organisation_id == org_id)
            .with_for_update()
        )
        if customer is None:
            raise HTTPException(status_code=404, detail="Customer not found.")
        cust_snap = {"id": customer.id, "name": customer.name, "email": customer.email, "phone": customer.phone}

    pos_state = (
        payload.place_of_supply_state
        or (customer.state_code if customer and customer.state_code else tax_profile.state_code)
    )
    is_interstate = pos_state != tax_profile.state_code

    prod_ids = sorted({i.product_id for i in payload.items})
    products = {
        p.id: p
        for p in db.scalars(
            select(CommerceProduct).where(
                CommerceProduct.organisation_id == org_id,
                CommerceProduct.id.in_(prod_ids),
            )
        ).all()
    }
    if len(products) != len(prod_ids):
        raise HTTPException(status_code=404, detail="One or more products not found.")

    campaign = None
    campaign_prods: dict[int, SurgeCampaignProduct] = {}
    if payload.campaign_id is not None:
        campaign = db.scalar(
            select(SurgeCampaign)
            .where(
                SurgeCampaign.id == payload.campaign_id,
                SurgeCampaign.organisation_id == org_id,
            )
            .with_for_update()
        )
        if campaign is None:
            raise HTTPException(status_code=404, detail="Surge campaign not found.")
        campaign_service._sync_campaign_expiry(campaign, now)
        if campaign.status != "ACTIVE" or not (campaign.starts_at <= now < campaign.ends_at):
            raise HTTPException(status_code=409, detail="Surge campaign is not currently active.")
        campaign_prods = {
            cp.product_id: cp
            for cp in db.scalars(
                select(SurgeCampaignProduct)
                .where(
                    SurgeCampaignProduct.campaign_id == campaign.id,
                    SurgeCampaignProduct.product_id.in_(prod_ids),
                )
                .order_by(SurgeCampaignProduct.product_id.asc())
                .with_for_update()
            ).all()
        }
        if len(campaign_prods) != len(prod_ids):
            raise HTTPException(status_code=409, detail="All POS campaign items must belong to the campaign.")

    # Compute item prices, discounts, CGST/SGST/IGST cleanly
    subtotal_minor = 0
    item_discount_total = 0
    cgst_total = 0
    sgst_total = 0
    igst_total = 0
    lines_prepared: list[tuple[CommerceProduct, int, int, int, int, int]] = []

    for item in payload.items:
        prod = products[item.product_id]
        eff_qty = item.quantity * item.unit_multiplier
        unit_price = prod.price_minor
        if campaign is not None:
            cp = campaign_prods[prod.id]
            if cp.sold_units + eff_qty > cp.allocated_units:
                raise HTTPException(status_code=409, detail=f"Campaign stock exhausted for SKU {prod.sku}.")
            cp.sold_units += eff_qty
            campaign.total_units_sold += eff_qty
            unit_price = cp.sale_price_minor

        taxable, l_cgst, l_sgst, l_igst, l_tax, line_tot = india_tax_service.compute_line_gst(
            unit_price_minor=unit_price,
            quantity=eff_qty,
            item_discount_minor=item.item_discount_minor,
            tax_rate_bps=prod.tax_rate_bps,
            tax_inclusive=bool(prod.tax_inclusive or tax_profile.tax_inclusive_default),
            is_interstate=is_interstate,
        )
        subtotal_minor += unit_price * eff_qty
        item_discount_total += item.item_discount_minor
        cgst_total += l_cgst
        sgst_total += l_sgst
        igst_total += l_igst
        lines_prepared.append((prod, eff_qty, unit_price, l_tax, line_tot, item.item_discount_minor))

    coupon_promo = None
    coupon_discount = 0
    cleaned_coupon = payload.coupon_code.strip().upper() if payload.coupon_code else None
    if cleaned_coupon:
        coupon_promo, coupon_discount = campaign_service.compute_coupon_discount(
            db, org_id, cleaned_coupon, subtotal_minor - item_discount_total, payload.customer_id, lock_row=True
        )

    total_discount = item_discount_total + payload.bill_discount_minor + coupon_discount
    tax_total = cgst_total + sgst_total + igst_total
    grand_total = max(0, (subtotal_minor + tax_total) - total_discount)

    # Validate payment split sum matches grand_total exactly
    split_sum = sum(p.amount_minor for p in payload.payments)
    if split_sum != grand_total:
        raise HTTPException(
            status_code=422,
            detail=f"Split payments sum ({split_sum}) must equal POS bill total ({grand_total}).",
        )

    has_razorpay = any(p.method == "razorpay" for p in payload.payments)
    methods_summary = "split" if len(payload.payments) > 1 else payload.payments[0].method
    is_paid = not has_razorpay

    # Lock & deduct inventory balances atomically (sorted product_id avoids deadlocks)
    req_by_prod: dict[int, int] = {}
    for prod, eff_qty, *_ in lines_prepared:
        req_by_prod[prod.id] = req_by_prod.get(prod.id, 0) + eff_qty

    order = Order(
        organisation_id=org_id,
        customer_id=payload.customer_id,
        order_number=f"POS-{org_id}-{now.strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}",
        currency="INR",
        subtotal_minor=subtotal_minor,
        discount_minor=total_discount,
        tax_minor=tax_total,
        total_minor=grand_total,
        order_status="PAID" if is_paid else "PENDING_PAYMENT",
        payment_status="CAPTURED" if is_paid else "PENDING",
        customer_snapshot=cust_snap,
        coupon_code=cleaned_coupon,
        promotion_id=coupon_promo.id if coupon_promo else None,
        campaign_id=campaign.id if campaign else None,
        source_channel="pos",
        payment_method=methods_summary,
        cashier_email=org_ctx.user.email,
        pos_shift_id=payload.shift_id,
        place_of_supply_state=pos_state,
        cgst_minor=cgst_total,
        sgst_minor=sgst_total,
        igst_minor=igst_total,
        offline_tx_id=payload.offline_tx_id.strip() if payload.offline_tx_id else None,
        placed_at=now,
    )
    db.add(order)
    db.flush()

    for prod, eff_qty, unit_price, l_tax, line_tot, _ in lines_prepared:
        db.add(
            OrderItem(
                organisation_id=org_id,
                order_id=order.id,
                product_id=prod.id,
                location_id=location.id,
                sku_snapshot=prod.sku,
                name_snapshot=prod.name,
                unit_price_minor=unit_price,
                tax_rate_bps=prod.tax_rate_bps,
                quantity=eff_qty,
                tax_minor=l_tax,
                line_total_minor=line_tot,
            )
        )

    for pid in sorted(req_by_prod):
        qty_needed = req_by_prod[pid]
        bal = inventory_service._get_or_create_balance_locked(db, org_id, pid, location.id)
        avail = bal.quantity - bal.reserved_quantity
        if not tax_profile.allow_negative_stock and avail < qty_needed:
            raise HTTPException(
                status_code=409,
                detail=f"Insufficient stock for product {pid} at {location.name} ({avail} available, {qty_needed} needed).",
            )
        bal.quantity -= qty_needed
        bal.last_movement_at = now
        bal.updated_at = now
        db.add(
            InventoryMovement(
                organisation_id=org_id,
                balance_id=bal.id,
                product_id=pid,
                location_id=location.id,
                movement_type="sale",
                quantity_delta=-qty_needed,
                reserved_delta=0,
                balance_after=bal.quantity,
                reserved_after=bal.reserved_quantity,
                reference_type="pos_order",
                reference_id=order.order_number,
                reason="POS checkout sale",
                actor_ref=org_ctx.user.email,
            )
        )

    if coupon_promo is not None:
        coupon_promo.used_count += 1
        db.add(
            PromotionRedemption(
                organisation_id=org_id,
                promotion_id=coupon_promo.id,
                order_id=order.id,
                customer_id=order.customer_id,
                discount_minor=coupon_discount,
            )
        )

    # Record split tenders & store credit deductions & shift drawer tallies
    shift = None
    if payload.shift_id is not None:
        shift = db.scalar(
            select(PosShift)
            .where(PosShift.id == payload.shift_id, PosShift.organisation_id == org_id, PosShift.status == "OPEN")
            .with_for_update()
        )
        if shift is None:
            raise HTTPException(status_code=409, detail="Specified POS shift is not open.")

    for sp in payload.payments:
        if sp.method == "store_credit":
            if customer is None:
                raise HTTPException(status_code=422, detail="Customer required for store credit redemption.")
            if customer.store_credit_minor < sp.amount_minor:
                raise HTTPException(status_code=409, detail="Insufficient customer store credit balance.")
            customer.store_credit_minor -= sp.amount_minor
            db.add(
                LoyaltyLedger(
                    organisation_id=org_id,
                    customer_id=customer.id,
                    order_id=order.id,
                    entry_type="CREDIT_USE",
                    points_delta=0,
                    store_credit_delta_minor=-sp.amount_minor,
                    reason=f"POS bill {order.order_number}",
                    actor_ref=org_ctx.user.email,
                )
            )
        db.add(
            OrderPaymentSplit(
                organisation_id=org_id,
                order_id=order.id,
                method=sp.method,
                amount_minor=sp.amount_minor,
                reference_utr=sp.reference_utr,
                verified=sp.method != "razorpay",
            )
        )
        if shift is not None:
            if sp.method == "cash":
                shift.cash_sales_minor += sp.amount_minor
                shift.expected_cash_minor += sp.amount_minor
            elif sp.method == "upi":
                shift.upi_sales_minor += sp.amount_minor
            elif sp.method == "card":
                shift.card_sales_minor += sp.amount_minor
            elif sp.method == "bank_transfer":
                shift.bank_sales_minor += sp.amount_minor

    if customer is not None and is_paid:
        pts_earned = grand_total // 10000  # 1 point per INR 100
        if pts_earned > 0:
            customer.loyalty_points += pts_earned
            if customer.loyalty_points >= 500:
                customer.tier = "platinum"
            elif customer.loyalty_points >= 150:
                customer.tier = "gold"
            elif customer.loyalty_points >= 50:
                customer.tier = "silver"
            db.add(
                LoyaltyLedger(
                    organisation_id=org_id,
                    customer_id=customer.id,
                    order_id=order.id,
                    entry_type="EARN",
                    points_delta=pts_earned,
                    store_credit_delta_minor=0,
                    reason=f"POS purchase {order.order_number}",
                    actor_ref=org_ctx.user.email,
                )
            )

    if payload.held_bill_id is not None:
        held = db.scalar(
            select(PosHeldBill).where(
                PosHeldBill.id == payload.held_bill_id,
                PosHeldBill.organisation_id == org_id,
            )
        )
        if held is not None:
            held.status = "RESUMED"

    inv_out = None
    if is_paid:
        sales_service.sync_sales_record_for_order(
            db, order, transaction_ref=f"{methods_summary.upper()}-{order.order_number}"
        )
        inv = india_tax_service.generate_invoice_for_order(db, org_id, order.id)
        inv_out = india_tax_service.to_invoice_out(inv)

    db.add(
        OrderEvent(
            organisation_id=org_id,
            order_id=order.id,
            from_status=None,
            to_status=order.order_status,
            event_type="pos_checkout_created",
            actor_ref=org_ctx.user.email,
            details={"method": methods_summary, "total_minor": grand_total, "cgst": cgst_total, "sgst": sgst_total, "igst": igst_total},
        )
    )
    db.add(
        AuditLog(
            organisation_id=org_id,
            actor_type=org_ctx.membership.role,
            actor_ref=org_ctx.user.email,
            action="pos_checkout_completed",
            entity_name="orders",
            entity_id=str(order.id),
            details={"order_number": order.order_number, "total_minor": grand_total, "payment_status": order.payment_status},
        )
    )
    db.commit()

    return PosCheckoutOut(
        order_id=str(order.id),
        order_number=order.order_number,
        order_status=order.order_status,
        payment_status=order.payment_status,
        invoice=inv_out,
        subtotal_minor=order.subtotal_minor,
        discount_minor=order.discount_minor,
        cgst_minor=order.cgst_minor,
        sgst_minor=order.sgst_minor,
        igst_minor=order.igst_minor,
        total_minor=order.total_minor,
        total=format_minor_to_decimal_str(order.total_minor),
        payments=[p.model_dump() for p in payload.payments],
        offline_replayed=False,
    )
