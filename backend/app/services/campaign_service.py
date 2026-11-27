from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.auth_dependencies import OrgContext
from app.models.campaigns import (
    Promotion,
    PromotionRedemption,
    SurgeCampaign,
    SurgeCampaignProduct,
)
from app.models.operations import SalesRecord
from app.models.retail import CommerceProduct, Order
from app.models.rossmann import AuditLog
from app.schemas.expansion import (
    CampaignProductOut,
    CouponValidateOut,
    CouponValidateRequest,
    PromotionCreate,
    PromotionOut,
    SurgeCampaignCreate,
    SurgeCampaignOut,
    SurgeCampaignTransition,
)
from app.schemas.retail import format_minor_to_decimal_str

VALID_CAMPAIGN_TRANSITIONS: dict[str, set[str]] = {
    "DRAFT": {"SCHEDULED", "ACTIVE", "CANCELLED"},
    "SCHEDULED": {"ACTIVE", "PAUSED", "CANCELLED"},
    "ACTIVE": {"PAUSED", "COMPLETED", "CANCELLED"},
    "PAUSED": {"ACTIVE", "COMPLETED", "CANCELLED"},
    "COMPLETED": set(),
    "CANCELLED": set(),
}


def _sync_campaign_expiry(campaign: SurgeCampaign, now: datetime) -> None:
    if campaign.status in ("SCHEDULED", "ACTIVE") and campaign.ends_at <= now:
        campaign.status = "COMPLETED"
        campaign.updated_at = now
    elif campaign.status == "SCHEDULED" and campaign.starts_at <= now < campaign.ends_at:
        campaign.status = "ACTIVE"
        campaign.updated_at = now


def _to_campaign_out(db: Session, campaign: SurgeCampaign) -> SurgeCampaignOut:
    cp_rows = list(
        db.scalars(
            select(SurgeCampaignProduct)
            .where(SurgeCampaignProduct.campaign_id == campaign.id)
            .order_by(SurgeCampaignProduct.id.asc())
        ).all()
    )
    prod_ids = [r.product_id for r in cp_rows]
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

    rev_row = db.execute(
        select(
            func.coalesce(func.sum(SalesRecord.net_amount_minor), 0).label("rev"),
            func.count(SalesRecord.id).label("cnt"),
        ).where(
            SalesRecord.organisation_id == campaign.organisation_id,
            SalesRecord.campaign_id == campaign.id,
        )
    ).first()
    rev_minor = int(rev_row.rev or 0) if rev_row else 0
    order_cnt = int(rev_row.cnt or 0) if rev_row else 0

    return SurgeCampaignOut(
        id=str(campaign.id),
        organisation_id=campaign.organisation_id,
        name=campaign.name,
        description=campaign.description,
        status=campaign.status,
        starts_at=campaign.starts_at,
        ends_at=campaign.ends_at,
        discount_type=campaign.discount_type,
        discount_value=campaign.discount_value,
        category_filter=campaign.category_filter,
        campaign_limit_units=campaign.campaign_limit_units,
        total_units_sold=campaign.total_units_sold,
        per_customer_limit=campaign.per_customer_limit,
        revenue_minor=rev_minor,
        revenue=format_minor_to_decimal_str(rev_minor),
        orders_generated=order_cnt,
        products=[
            CampaignProductOut(
                id=str(cp.id),
                product_id=str(cp.product_id),
                sku=prods[cp.product_id].sku if cp.product_id in prods else "",
                product_name=prods[cp.product_id].name if cp.product_id in prods else f"Product #{cp.product_id}",
                original_price_minor=cp.original_price_minor,
                original_price=format_minor_to_decimal_str(cp.original_price_minor),
                sale_price_minor=cp.sale_price_minor,
                sale_price=format_minor_to_decimal_str(cp.sale_price_minor),
                allocated_units=cp.allocated_units,
                sold_units=cp.sold_units,
                remaining_units=max(0, cp.allocated_units - cp.sold_units),
            )
            for cp in cp_rows
        ],
        created_by=campaign.created_by,
        created_at=campaign.created_at,
    )


def create_campaign(
    db: Session, org_ctx: OrgContext, payload: SurgeCampaignCreate
) -> SurgeCampaignOut:
    org_id = org_ctx.organisation.id
    if payload.ends_at <= payload.starts_at:
        raise HTTPException(status_code=422, detail="Campaign end time must be after start time.")
    if payload.discount_type == "percentage" and payload.discount_value > 9500:
        raise HTTPException(
            status_code=422, detail="Percentage discount in bps cannot exceed 9500 (95%)."
        )

    now = datetime.now(timezone.utc)
    if payload.activate_immediately:
        initial_status = "ACTIVE" if payload.starts_at <= now < payload.ends_at else "SCHEDULED"
    else:
        initial_status = "DRAFT"

    campaign = SurgeCampaign(
        organisation_id=org_id,
        name=payload.name.strip(),
        description=payload.description,
        status=initial_status,
        starts_at=payload.starts_at,
        ends_at=payload.ends_at,
        discount_type=payload.discount_type,
        discount_value=payload.discount_value,
        category_filter=payload.category_filter,
        campaign_limit_units=payload.campaign_limit_units,
        total_units_sold=0,
        per_customer_limit=payload.per_customer_limit,
        created_by=org_ctx.user.email,
    )
    db.add(campaign)
    db.flush()

    seen_products: set[int] = set()
    for item in payload.products:
        if item.product_id in seen_products:
            raise HTTPException(status_code=422, detail="Duplicate product in campaign.")
        seen_products.add(item.product_id)
        prod = db.scalar(
            select(CommerceProduct).where(
                CommerceProduct.id == item.product_id,
                CommerceProduct.organisation_id == org_id,
            )
        )
        if prod is None:
            raise HTTPException(status_code=404, detail=f"Product {item.product_id} not found.")

        if item.sale_price_minor is not None:
            sale_price = item.sale_price_minor
        elif payload.discount_type == "percentage":
            sale_price = max(0, prod.price_minor - (prod.price_minor * payload.discount_value // 10000))
        else:
            sale_price = max(0, prod.price_minor - payload.discount_value)

        db.add(
            SurgeCampaignProduct(
                organisation_id=org_id,
                campaign_id=campaign.id,
                product_id=prod.id,
                original_price_minor=prod.price_minor,
                sale_price_minor=sale_price,
                allocated_units=item.allocated_units,
                sold_units=0,
            )
        )

    db.add(
        AuditLog(
            organisation_id=org_id,
            actor_type=org_ctx.membership.role,
            actor_ref=org_ctx.user.email,
            action="surge_campaign_created",
            entity_name="surge_campaigns",
            entity_id=str(campaign.id),
            details={"name": campaign.name, "status": campaign.status},
        )
    )
    db.commit()
    db.refresh(campaign)
    return _to_campaign_out(db, campaign)


def list_campaigns(
    db: Session, org_id: int, status: str | None = None
) -> list[SurgeCampaignOut]:
    campaigns = list(
        db.scalars(
            select(SurgeCampaign)
            .where(SurgeCampaign.organisation_id == org_id)
            .order_by(SurgeCampaign.id.desc())
        ).all()
    )
    now = datetime.now(timezone.utc)
    dirty = False
    for c in campaigns:
        before = c.status
        _sync_campaign_expiry(c, now)
        if c.status != before:
            dirty = True
    if dirty:
        db.commit()

    if status:
        target = status.upper()
        campaigns = [c for c in campaigns if c.status == target]

    return [_to_campaign_out(db, c) for c in campaigns]


def transition_campaign(
    db: Session, org_ctx: OrgContext, campaign_id: int, payload: SurgeCampaignTransition
) -> SurgeCampaignOut:
    org_id = org_ctx.organisation.id
    campaign = db.scalar(
        select(SurgeCampaign)
        .where(
            SurgeCampaign.id == campaign_id,
            SurgeCampaign.organisation_id == org_id,
        )
        .with_for_update()
    )
    if campaign is None:
        raise HTTPException(status_code=404, detail="Campaign not found.")

    now = datetime.now(timezone.utc)
    _sync_campaign_expiry(campaign, now)

    allowed = VALID_CAMPAIGN_TRANSITIONS.get(campaign.status, set())
    if payload.target_status not in allowed:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot transition campaign from {campaign.status} to {payload.target_status}.",
        )
    if payload.target_status == "ACTIVE" and campaign.ends_at <= now:
        raise HTTPException(status_code=409, detail="Cannot activate an expired campaign.")

    campaign.status = payload.target_status
    campaign.updated_at = now
    db.add(
        AuditLog(
            organisation_id=org_id,
            actor_type=org_ctx.membership.role,
            actor_ref=org_ctx.user.email,
            action="surge_campaign_transitioned",
            entity_name="surge_campaigns",
            entity_id=str(campaign.id),
            details={"to_status": campaign.status},
        )
    )
    db.commit()
    db.refresh(campaign)
    return _to_campaign_out(db, campaign)


def _to_promotion_out(p: Promotion) -> PromotionOut:
    return PromotionOut(
        id=str(p.id),
        organisation_id=p.organisation_id,
        code=p.code,
        name=p.name,
        description=p.description,
        discount_type=p.discount_type,
        discount_value=p.discount_value,
        min_order_minor=p.min_order_minor,
        min_order=format_minor_to_decimal_str(p.min_order_minor),
        max_discount_minor=p.max_discount_minor,
        max_discount=(
            format_minor_to_decimal_str(p.max_discount_minor)
            if p.max_discount_minor is not None
            else None
        ),
        usage_limit=p.usage_limit,
        used_count=p.used_count,
        per_customer_limit=p.per_customer_limit,
        customer_id=p.customer_id,
        starts_at=p.starts_at,
        ends_at=p.ends_at,
        is_active=p.is_active,
        created_at=p.created_at,
    )


def create_promotion(
    db: Session, org_ctx: OrgContext, payload: PromotionCreate
) -> PromotionOut:
    org_id = org_ctx.organisation.id
    if payload.discount_type == "percentage" and payload.discount_value > 9500:
        raise HTTPException(status_code=422, detail="Percentage discount bps cannot exceed 9500.")
    if payload.starts_at and payload.ends_at and payload.ends_at <= payload.starts_at:
        raise HTTPException(status_code=422, detail="Coupon end time must be after start time.")

    promo = Promotion(
        organisation_id=org_id,
        code=payload.code.strip().upper(),
        name=payload.name.strip(),
        description=payload.description,
        discount_type=payload.discount_type,
        discount_value=payload.discount_value,
        min_order_minor=payload.min_order_minor,
        max_discount_minor=payload.max_discount_minor,
        usage_limit=payload.usage_limit,
        used_count=0,
        per_customer_limit=payload.per_customer_limit,
        customer_id=payload.customer_id,
        starts_at=payload.starts_at,
        ends_at=payload.ends_at,
        is_active=payload.is_active,
    )
    try:
        db.add(promo)
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Coupon code already exists in this organisation.") from exc

    db.add(
        AuditLog(
            organisation_id=org_id,
            actor_type=org_ctx.membership.role,
            actor_ref=org_ctx.user.email,
            action="promotion_created",
            entity_name="promotions",
            entity_id=str(promo.id),
            details={"code": promo.code, "discount_type": promo.discount_type},
        )
    )
    db.commit()
    db.refresh(promo)
    return _to_promotion_out(promo)


def list_promotions(db: Session, org_id: int) -> list[PromotionOut]:
    rows = db.scalars(
        select(Promotion)
        .where(Promotion.organisation_id == org_id)
        .order_by(Promotion.id.desc())
    ).all()
    return [_to_promotion_out(p) for p in rows]


def compute_coupon_discount(
    db: Session,
    org_id: int,
    code: str,
    subtotal_minor: int,
    customer_id: int | None,
    *,
    lock_row: bool = False,
) -> tuple[Promotion, int]:
    cleaned = code.strip().upper()
    stmt = select(Promotion).where(
        Promotion.organisation_id == org_id,
        Promotion.code == cleaned,
    )
    if lock_row:
        stmt = stmt.with_for_update()
    promo = db.scalar(stmt)
    if promo is None:
        raise HTTPException(status_code=404, detail="Coupon code not found.")
    if not promo.is_active:
        raise HTTPException(status_code=409, detail="Coupon code is inactive.")

    now = datetime.now(timezone.utc)
    if promo.starts_at and now < promo.starts_at:
        raise HTTPException(status_code=409, detail="Coupon code is not yet active.")
    if promo.ends_at and now >= promo.ends_at:
        raise HTTPException(status_code=409, detail="Coupon code has expired.")
    if subtotal_minor < promo.min_order_minor:
        raise HTTPException(
            status_code=409,
            detail=f"Order subtotal must be at least {format_minor_to_decimal_str(promo.min_order_minor)} to apply this coupon.",
        )
    if promo.usage_limit is not None and promo.used_count >= promo.usage_limit:
        raise HTTPException(status_code=409, detail="Coupon usage limit reached.")
    if promo.customer_id is not None and customer_id != promo.customer_id:
        raise HTTPException(status_code=409, detail="Coupon is restricted to a different customer.")
    if promo.per_customer_limit is not None and customer_id is not None:
        used_by_cust = db.scalar(
            select(func.count(PromotionRedemption.id)).where(
                PromotionRedemption.promotion_id == promo.id,
                PromotionRedemption.customer_id == customer_id,
            )
        ) or 0
        if int(used_by_cust) >= promo.per_customer_limit:
            raise HTTPException(
                status_code=409,
                detail="Customer redemption limit reached for this coupon.",
            )

    if promo.discount_type == "percentage":
        discount = (subtotal_minor * promo.discount_value) // 10000
    else:
        discount = promo.discount_value

    if promo.max_discount_minor is not None:
        discount = min(discount, promo.max_discount_minor)
    discount = min(discount, subtotal_minor)
    return promo, max(0, int(discount))


def validate_coupon(
    db: Session, org_id: int, payload: CouponValidateRequest
) -> CouponValidateOut:
    try:
        _, discount = compute_coupon_discount(
            db,
            org_id,
            payload.code,
            payload.subtotal_minor,
            payload.customer_id,
            lock_row=False,
        )
        return CouponValidateOut(
            valid=True,
            code=payload.code.strip().upper(),
            discount_minor=discount,
            discount=format_minor_to_decimal_str(discount),
            reason=None,
        )
    except HTTPException as exc:
        return CouponValidateOut(
            valid=False,
            code=payload.code.strip().upper(),
            discount_minor=0,
            discount="0.00",
            reason=str(exc.detail),
        )
