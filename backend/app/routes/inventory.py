from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.auth_dependencies import OrgContext, require_org_roles
from app.core.database import get_db
from app.schemas.retail import (
    InventoryAdjustmentCreate,
    InventoryBalanceListResponse,
    InventoryBalanceOut,
    InventoryLocationCreate,
    InventoryLocationOut,
    InventoryMovementListResponse,
)
from app.services import inventory_service

router = APIRouter(prefix="/api/v1/inventory", tags=["Commerce Inventory"])


@router.get("/locations", response_model=list[InventoryLocationOut])
def list_locations(
    org_ctx: OrgContext = Depends(
        require_org_roles("owner", "admin", "analyst", "operator")
    ),
    db: Session = Depends(get_db),
):
    return inventory_service.list_locations(db, org_ctx.organisation.id)


@router.post("/locations", response_model=InventoryLocationOut, status_code=201)
def create_location(
    payload: InventoryLocationCreate,
    org_ctx: OrgContext = Depends(require_org_roles("owner", "admin", "operator")),
    db: Session = Depends(get_db),
):
    return inventory_service.create_location(db, org_ctx, payload)


@router.get("", response_model=InventoryBalanceListResponse)
def list_inventory(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100, alias="pageSize"),
    search: str | None = Query(None, max_length=200),
    location_id: int | None = Query(None, gt=0, alias="locationId"),
    org_ctx: OrgContext = Depends(
        require_org_roles("owner", "admin", "analyst", "operator")
    ),
    db: Session = Depends(get_db),
):
    return inventory_service.list_balances(
        db,
        org_ctx.organisation.id,
        page=page,
        page_size=page_size,
        search=search,
        location_id=location_id,
    )


@router.post("/adjustments", response_model=InventoryBalanceOut)
def adjust_inventory(
    payload: InventoryAdjustmentCreate,
    org_ctx: OrgContext = Depends(require_org_roles("owner", "admin", "operator")),
    db: Session = Depends(get_db),
):
    return inventory_service.adjust_stock(db, org_ctx, payload)


@router.get("/movements", response_model=InventoryMovementListResponse)
def list_movements(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100, alias="pageSize"),
    search: str | None = Query(None, max_length=200),
    org_ctx: OrgContext = Depends(
        require_org_roles("owner", "admin", "analyst", "operator")
    ),
    db: Session = Depends(get_db),
):
    return inventory_service.list_movements(
        db,
        org_ctx.organisation.id,
        page=page,
        page_size=page_size,
        search=search,
    )


@router.post("/reservations/expire")
def expire_reservations(
    org_ctx: OrgContext = Depends(require_org_roles("owner", "admin", "operator")),
    db: Session = Depends(get_db),
):
    expired_orders = inventory_service.expire_stale_reservations(
        db,
        organisation_id=org_ctx.organisation.id,
        actor_ref=org_ctx.user.email,
    )
    return {"expired_orders": expired_orders}
