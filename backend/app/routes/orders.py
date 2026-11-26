from fastapi import APIRouter, Depends, Header, Query
from sqlalchemy.orm import Session

from app.core.auth_dependencies import OrgContext, require_org_roles
from app.core.database import get_db
from app.schemas.retail import (
    OrderCreate,
    OrderListResponse,
    OrderOut,
    OrderTransitionRequest,
)
from app.services import order_service

router = APIRouter(prefix="/api/v1/orders", tags=["Commerce Orders"])


@router.post("", response_model=OrderOut, status_code=201)
def create_order(
    payload: OrderCreate,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    org_ctx: OrgContext = Depends(require_org_roles("owner", "admin", "operator")),
    db: Session = Depends(get_db),
):
    return order_service.create_order(
        db, org_ctx, payload, idempotency_key=idempotency_key
    )


@router.get("", response_model=OrderListResponse)
def list_orders(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100, alias="pageSize"),
    search: str | None = Query(None, max_length=200),
    status: str | None = Query(None),
    org_ctx: OrgContext = Depends(
        require_org_roles("owner", "admin", "analyst", "operator")
    ),
    db: Session = Depends(get_db),
):
    return order_service.list_orders(
        db,
        org_ctx.organisation.id,
        page=page,
        page_size=page_size,
        search=search,
        status=status,
    )


@router.get("/{order_id}", response_model=OrderOut)
def get_order(
    order_id: int,
    org_ctx: OrgContext = Depends(
        require_org_roles("owner", "admin", "analyst", "operator")
    ),
    db: Session = Depends(get_db),
):
    return order_service.get_order(db, org_ctx.organisation.id, order_id)


@router.post("/{order_id}/transition", response_model=OrderOut)
def transition_order(
    order_id: int,
    payload: OrderTransitionRequest,
    org_ctx: OrgContext = Depends(require_org_roles("owner", "admin", "operator")),
    db: Session = Depends(get_db),
):
    return order_service.transition_order(db, org_ctx, order_id, payload)
