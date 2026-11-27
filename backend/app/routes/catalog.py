from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.auth_dependencies import OrgContext, require_org_roles
from app.core.database import get_db
from app.schemas.retail import (
    CommerceProductCreate,
    CommerceProductListResponse,
    CommerceProductOut,
    CommerceProductUpdate,
)
from app.services import catalog_service

router = APIRouter(prefix="/api/v1/products", tags=["Commerce Catalog"])


@router.post("", response_model=CommerceProductOut, status_code=201)
def create_product(
    payload: CommerceProductCreate,
    org_ctx: OrgContext = Depends(require_org_roles("owner", "admin", "operator")),
    db: Session = Depends(get_db),
):
    return catalog_service.create_product(db, org_ctx, payload)


@router.get("", response_model=CommerceProductListResponse)
def list_products(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100, alias="pageSize"),
    search: str | None = Query(None, max_length=200),
    status: str | None = Query(None),
    category: str | None = Query(None),
    org_ctx: OrgContext = Depends(
        require_org_roles("owner", "admin", "analyst", "operator")
    ),
    db: Session = Depends(get_db),
):
    return catalog_service.list_products(
        db,
        org_ctx.organisation.id,
        page=page,
        page_size=page_size,
        search=search,
        status=status,
        category=category,
    )


@router.get("/{product_id}", response_model=CommerceProductOut)
def get_product(
    product_id: int,
    org_ctx: OrgContext = Depends(
        require_org_roles("owner", "admin", "analyst", "operator")
    ),
    db: Session = Depends(get_db),
):
    return catalog_service.get_product(db, org_ctx.organisation.id, product_id)


@router.patch("/{product_id}", response_model=CommerceProductOut)
def update_product(
    product_id: int,
    payload: CommerceProductUpdate,
    org_ctx: OrgContext = Depends(require_org_roles("owner", "admin", "operator")),
    db: Session = Depends(get_db),
):
    return catalog_service.update_product(db, org_ctx, product_id, payload)
