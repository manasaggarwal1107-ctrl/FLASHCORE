from fastapi import APIRouter, Depends, Header, Query
from sqlalchemy.orm import Session

from app.core.auth_dependencies import OrgContext, require_org_roles
from app.core.database import get_db
from app.schemas.finance import (
    PaymentLinkCreateRequest,
    PaymentLinkListResponse,
    PaymentLinkOut,
    RefundCreateRequest,
    RefundDecisionRequest,
    RefundListResponse,
    RefundOut,
    RefundPolicyOut,
    RefundPolicyUpdate,
)
from app.services import payment_link_service, refund_service

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


@router.post("/links", response_model=PaymentLinkOut, status_code=201)
def create_payment_link(
    payload: PaymentLinkCreateRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    org_ctx: OrgContext = Depends(require_org_roles("owner", "admin", "operator")),
    db: Session = Depends(get_db),
):
    return payment_link_service.create_payment_link(
        db, org_ctx, payload, idempotency_key=idempotency_key
    )


@router.get("/links", response_model=PaymentLinkListResponse)
def list_payment_links(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100, alias="pageSize"),
    status: str | None = Query(None),
    org_ctx: OrgContext = Depends(
        require_org_roles("owner", "admin", "analyst", "operator")
    ),
    db: Session = Depends(get_db),
):
    return payment_link_service.list_payment_links(
        db, org_ctx.organisation.id, page=page, page_size=page_size, status=status
    )


@router.get("/links/{link_id}", response_model=PaymentLinkOut)
def get_payment_link(
    link_id: int,
    org_ctx: OrgContext = Depends(
        require_org_roles("owner", "admin", "analyst", "operator")
    ),
    db: Session = Depends(get_db),
):
    return payment_link_service.get_payment_link(db, org_ctx.organisation.id, link_id)


@router.post("/links/{link_id}/cancel", response_model=PaymentLinkOut)
def cancel_payment_link(
    link_id: int,
    org_ctx: OrgContext = Depends(require_org_roles("owner", "admin", "operator")),
    db: Session = Depends(get_db),
):
    return payment_link_service.cancel_payment_link(db, org_ctx, link_id)


@router.post("/links/{link_id}/sync", response_model=PaymentLinkOut)
def sync_payment_link(
    link_id: int,
    org_ctx: OrgContext = Depends(require_org_roles("owner", "admin", "operator")),
    db: Session = Depends(get_db),
):
    return payment_link_service.sync_payment_link(db, org_ctx, link_id)
