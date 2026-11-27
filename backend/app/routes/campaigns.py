from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.auth_dependencies import OrgContext, require_org_roles
from app.core.database import get_db
from app.schemas.expansion import (
    CouponValidateOut,
    CouponValidateRequest,
    PromotionCreate,
    PromotionOut,
    SurgeCampaignCreate,
    SurgeCampaignOut,
    SurgeCampaignTransition,
)
from app.services import campaign_service

router = APIRouter(prefix="/api/v1", tags=["Surge Campaigns & Promotions"])


@router.get("/campaigns", response_model=list[SurgeCampaignOut])
def list_campaigns(
    status: str | None = Query(None),
    org_ctx: OrgContext = Depends(
        require_org_roles("owner", "admin", "analyst", "operator")
    ),
    db: Session = Depends(get_db),
):
    return campaign_service.list_campaigns(db, org_ctx.organisation.id, status=status)


@router.post("/campaigns", response_model=SurgeCampaignOut, status_code=201)
def create_campaign(
    payload: SurgeCampaignCreate,
    org_ctx: OrgContext = Depends(require_org_roles("owner", "admin", "operator")),
    db: Session = Depends(get_db),
):
    return campaign_service.create_campaign(db, org_ctx, payload)


@router.post("/campaigns/{campaign_id}/transition", response_model=SurgeCampaignOut)
def transition_campaign(
    campaign_id: int,
    payload: SurgeCampaignTransition,
    org_ctx: OrgContext = Depends(require_org_roles("owner", "admin", "operator")),
    db: Session = Depends(get_db),
):
    return campaign_service.transition_campaign(db, org_ctx, campaign_id, payload)


@router.get("/promotions", response_model=list[PromotionOut])
def list_promotions(
    org_ctx: OrgContext = Depends(
        require_org_roles("owner", "admin", "analyst", "operator")
    ),
    db: Session = Depends(get_db),
):
    return campaign_service.list_promotions(db, org_ctx.organisation.id)


@router.post("/promotions", response_model=PromotionOut, status_code=201)
def create_promotion(
    payload: PromotionCreate,
    org_ctx: OrgContext = Depends(require_org_roles("owner", "admin", "operator")),
    db: Session = Depends(get_db),
):
    return campaign_service.create_promotion(db, org_ctx, payload)


@router.post("/promotions/validate", response_model=CouponValidateOut)
def validate_promotion_code(
    payload: CouponValidateRequest,
    org_ctx: OrgContext = Depends(
        require_org_roles("owner", "admin", "analyst", "operator")
    ),
    db: Session = Depends(get_db),
):
    return campaign_service.validate_coupon(db, org_ctx.organisation.id, payload)
