from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.auth_dependencies import OrgContext, require_org_roles
from app.core.database import get_db
from app.schemas.expansion import (
    DamagedStockAdjustRequest,
    InventoryIntelligenceOut,
    PurchaseOrderCreate,
    PurchaseOrderOut,
    PurchaseOrderReceiveRequest,
    StockTransferCreate,
    StockTransferOut,
    SupplierCreate,
    SupplierOut,
    WarehouseCreate,
    WarehouseOut,
)
from app.services import inventory_ops_service, procurement_service

router = APIRouter(prefix="/api/v1", tags=["Warehouses & Procurement"])


@router.get("/warehouses", response_model=list[WarehouseOut])
def list_warehouses(
    org_ctx: OrgContext = Depends(
        require_org_roles("owner", "admin", "analyst", "operator")
    ),
    db: Session = Depends(get_db),
):
    return inventory_ops_service.list_warehouses_with_stats(db, org_ctx.organisation.id)


@router.post("/warehouses", response_model=WarehouseOut, status_code=201)
def create_warehouse(
    payload: WarehouseCreate,
    org_ctx: OrgContext = Depends(require_org_roles("owner", "admin")),
    db: Session = Depends(get_db),
):
    return inventory_ops_service.create_warehouse(db, org_ctx, payload)


@router.post("/retail-inventory/damaged")
def adjust_damaged_stock(
    payload: DamagedStockAdjustRequest,
    org_ctx: OrgContext = Depends(require_org_roles("owner", "admin", "operator")),
    db: Session = Depends(get_db),
):
    return inventory_ops_service.adjust_damaged_stock(db, org_ctx, payload)


@router.get("/retail-inventory/intelligence", response_model=InventoryIntelligenceOut)
def get_inventory_intelligence(
    org_ctx: OrgContext = Depends(
        require_org_roles("owner", "admin", "analyst", "operator")
    ),
    db: Session = Depends(get_db),
):
    return inventory_ops_service.get_inventory_intelligence(db, org_ctx.organisation.id)


@router.get("/transfers", response_model=list[StockTransferOut])
def list_transfers(
    status: str | None = Query(None),
    org_ctx: OrgContext = Depends(
        require_org_roles("owner", "admin", "analyst", "operator")
    ),
    db: Session = Depends(get_db),
):
    return inventory_ops_service.list_stock_transfers(
        db, org_ctx.organisation.id, status=status
    )


@router.post("/transfers", response_model=StockTransferOut, status_code=201)
def create_transfer(
    payload: StockTransferCreate,
    org_ctx: OrgContext = Depends(require_org_roles("owner", "admin", "operator")),
    db: Session = Depends(get_db),
):
    return inventory_ops_service.create_stock_transfer(db, org_ctx, payload)


@router.post("/transfers/{transfer_id}/approve", response_model=StockTransferOut)
def approve_transfer(
    transfer_id: int,
    org_ctx: OrgContext = Depends(require_org_roles("owner", "admin")),
    db: Session = Depends(get_db),
):
    return inventory_ops_service.approve_stock_transfer(db, org_ctx, transfer_id)


@router.post("/transfers/{transfer_id}/dispatch", response_model=StockTransferOut)
def dispatch_transfer(
    transfer_id: int,
    org_ctx: OrgContext = Depends(require_org_roles("owner", "admin", "operator")),
    db: Session = Depends(get_db),
):
    return inventory_ops_service.dispatch_stock_transfer(db, org_ctx, transfer_id)


@router.post("/transfers/{transfer_id}/receive", response_model=StockTransferOut)
def receive_transfer(
    transfer_id: int,
    org_ctx: OrgContext = Depends(require_org_roles("owner", "admin", "operator")),
    db: Session = Depends(get_db),
):
    return inventory_ops_service.receive_stock_transfer(db, org_ctx, transfer_id)


@router.get("/suppliers", response_model=list[SupplierOut])
def list_suppliers(
    org_ctx: OrgContext = Depends(
        require_org_roles("owner", "admin", "analyst", "operator")
    ),
    db: Session = Depends(get_db),
):
    return procurement_service.list_suppliers(db, org_ctx.organisation.id)


@router.post("/suppliers", response_model=SupplierOut, status_code=201)
def create_supplier(
    payload: SupplierCreate,
    org_ctx: OrgContext = Depends(require_org_roles("owner", "admin", "operator")),
    db: Session = Depends(get_db),
):
    return procurement_service.create_supplier(db, org_ctx, payload)


@router.get("/purchase-orders", response_model=list[PurchaseOrderOut])
def list_purchase_orders(
    status: str | None = Query(None),
    org_ctx: OrgContext = Depends(
        require_org_roles("owner", "admin", "analyst", "operator")
    ),
    db: Session = Depends(get_db),
):
    return procurement_service.list_purchase_orders(
        db, org_ctx.organisation.id, status=status
    )


@router.post("/purchase-orders", response_model=PurchaseOrderOut, status_code=201)
def create_purchase_order(
    payload: PurchaseOrderCreate,
    org_ctx: OrgContext = Depends(require_org_roles("owner", "admin", "operator")),
    db: Session = Depends(get_db),
):
    return procurement_service.create_purchase_order(db, org_ctx, payload)


@router.post("/purchase-orders/{po_id}/submit", response_model=PurchaseOrderOut)
def submit_purchase_order(
    po_id: int,
    org_ctx: OrgContext = Depends(require_org_roles("owner", "admin", "operator")),
    db: Session = Depends(get_db),
):
    return procurement_service.submit_purchase_order(db, org_ctx, po_id)


@router.post("/purchase-orders/{po_id}/receive", response_model=PurchaseOrderOut)
def receive_purchase_order(
    po_id: int,
    payload: PurchaseOrderReceiveRequest,
    org_ctx: OrgContext = Depends(require_org_roles("owner", "admin", "operator")),
    db: Session = Depends(get_db),
):
    return procurement_service.receive_purchase_order(db, org_ctx, po_id, payload)
