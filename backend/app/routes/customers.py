from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.auth_dependencies import OrgContext, require_org_roles
from app.core.database import get_db
from app.schemas.retail import (
    CustomerCreate,
    CustomerListResponse,
    CustomerOut,
    OrderListResponse,
)
from app.services import customer_service, order_service

router = APIRouter(prefix="/api/v1/customers", tags=["Commerce Customers"])


@router.post("", response_model=CustomerOut, status_code=201)
def create_customer(
    payload: CustomerCreate,
    org_ctx: OrgContext = Depends(require_org_roles("owner", "admin", "operator")),
    db: Session = Depends(get_db),
):
    return customer_service.create_customer(db, org_ctx, payload)


@router.get("", response_model=CustomerListResponse)
def list_customers(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100, alias="pageSize"),
    search: str | None = Query(None, max_length=200),
    status: str | None = Query(None),
    org_ctx: OrgContext = Depends(
        require_org_roles("owner", "admin", "analyst", "operator")
    ),
    db: Session = Depends(get_db),
):
    return customer_service.list_customers(
        db,
        org_ctx.organisation.id,
        page=page,
        page_size=page_size,
        search=search,
        status=status,
    )


@router.get("/{customer_id}", response_model=CustomerOut)
def get_customer(
    customer_id: int,
    org_ctx: OrgContext = Depends(
        require_org_roles("owner", "admin", "analyst", "operator")
    ),
    db: Session = Depends(get_db),
):
    return customer_service.get_customer(db, org_ctx.organisation.id, customer_id)


@router.get("/{customer_id}/orders", response_model=OrderListResponse)
def list_customer_orders(
    customer_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100, alias="pageSize"),
    org_ctx: OrgContext = Depends(
        require_org_roles("owner", "admin", "analyst", "operator")
    ),
    db: Session = Depends(get_db),
):
    customer_service.get_customer(db, org_ctx.organisation.id, customer_id)
    return order_service.list_orders(
        db,
        org_ctx.organisation.id,
        page=page,
        page_size=page_size,
        customer_id=customer_id,
    )
