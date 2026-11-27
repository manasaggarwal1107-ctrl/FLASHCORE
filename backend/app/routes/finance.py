from fastapi import APIRouter, Depends, Header, Query
from sqlalchemy.orm import Session

from app.core.auth_dependencies import OrgContext, require_org_roles
from app.core.database import get_db
from app.schemas.finance import (
    RefundCreateRequest,
    RefundDecisionRequest,
    RefundListResponse,
    RefundOut,
    RefundPolicyOut,
    RefundPolicyUpdate,
)
from app.services import refund_service

router = APIRouter(prefix="/api/v1/payments", tags=["Financial Operations"])


@router.get("/policies/refunds", response_model=RefundPolicyOut)
def get_refund_policy(
    org_ctx: OrgContext = Depends(
        require_org_roles("owner", "admin", "analyst", "operator")
    ),
    db: Session = Depends(get_db),
):
    return refund_service.get_refund_policy_out(db, org_ctx.organisation.id)


@router.put("/policies/refunds", response_model=RefundPolicyOut)
def update_refund_policy(
    payload: RefundPolicyUpdate,
    org_ctx: OrgContext = Depends(require_org_roles("owner", "admin")),
    db: Session = Depends(get_db),
):
    return refund_service.update_refund_policy(db, org_ctx, payload)


@router.post(
    "/transactions/{transaction_id}/refunds",
    response_model=RefundOut,
    status_code=201,
)
def create_refund(
    transaction_id: int,
    payload: RefundCreateRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    org_ctx: OrgContext = Depends(require_org_roles("owner", "admin", "operator")),
    db: Session = Depends(get_db),
):
    return refund_service.request_refund(
        db,
        org_ctx,
        transaction_id,
        payload,
        idempotency_key=idempotency_key,
    )


@router.get("/refunds", response_model=RefundListResponse)
def list_refunds(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100, alias="pageSize"),
    status: str | None = Query(None),
    org_ctx: OrgContext = Depends(
        require_org_roles("owner", "admin", "analyst", "operator")
    ),
    db: Session = Depends(get_db),
):
    return refund_service.list_refunds(
        db, org_ctx.organisation.id, page=page, page_size=page_size, status=status
    )


@router.get("/refunds/{refund_id}", response_model=RefundOut)
def get_refund(
    refund_id: int,
    org_ctx: OrgContext = Depends(
        require_org_roles("owner", "admin", "analyst", "operator")
    ),
    db: Session = Depends(get_db),
):
    return refund_service.get_refund(db, org_ctx.organisation.id, refund_id)


@router.post("/refunds/{refund_id}/approve", response_model=RefundOut)
def approve_refund(
    refund_id: int,
    payload: RefundDecisionRequest | None = None,
    org_ctx: OrgContext = Depends(require_org_roles("owner", "admin")),
    db: Session = Depends(get_db),
):
    return refund_service.approve_refund(
        db, org_ctx, refund_id, payload.decision_note if payload else None
    )


@router.post("/refunds/{refund_id}/reject", response_model=RefundOut)
def reject_refund(
    refund_id: int,
    payload: RefundDecisionRequest | None = None,
    org_ctx: OrgContext = Depends(require_org_roles("owner", "admin")),
    db: Session = Depends(get_db),
):
    return refund_service.reject_refund(
        db, org_ctx, refund_id, payload.decision_note if payload else None
    )


@router.post("/refunds/{refund_id}/sync", response_model=RefundOut)
def sync_refund(
    refund_id: int,
    org_ctx: OrgContext = Depends(require_org_roles("owner", "admin", "operator")),
    db: Session = Depends(get_db),
):
    return refund_service.sync_refund(db, org_ctx, refund_id)
