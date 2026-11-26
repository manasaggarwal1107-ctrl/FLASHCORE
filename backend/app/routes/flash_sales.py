
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core.database import get_db
from app.core.auth_dependencies import require_roles
from app.models.flash_sale import FlashSale, FlashSaleProduct
from app.models.commerce import Inventory, Product
from app.schemas.flash_sale import (
    FlashSaleCreate,
    FlashSaleOut,
    FlashSaleProductCreate,
    FlashSaleProductOut,
)

router = APIRouter(prefix="/api/flash-sales", tags=["Flash Sales"])


# CREATE CAMPAIGN
@router.post("", response_model=FlashSaleOut, status_code=201, dependencies=[Depends(require_roles("admin", "operator"))])
def create_flash_sale(
    data: FlashSaleCreate,
    db: Session = Depends(get_db)
):
    sale = FlashSale(
        **data.model_dump(),
        status="draft",
        origin="manual"
    )

    db.add(sale)
    db.commit()
    db.refresh(sale)

    return sale


# LIST CAMPAIGNS
@router.get("", response_model=list[FlashSaleOut], dependencies=[Depends(require_roles("admin", "analyst", "operator"))])
def list_flash_sales(db: Session = Depends(get_db)):
    return db.scalars(
        select(FlashSale).order_by(FlashSale.id.desc())
    ).all()


# ACTIVATE OR SCHEDULE A CAMPAIGN
@router.post("/{sale_id}/activate", response_model=FlashSaleOut, dependencies=[Depends(require_roles("admin", "operator"))])
def activate_flash_sale(
    sale_id: int,
    db: Session = Depends(get_db)
):
    sale = db.scalar(
        select(FlashSale)
        .where(FlashSale.id == sale_id)
        .with_for_update()
    )

    if not sale:
        raise HTTPException(404, "Flash sale not found")

    if sale.status != "draft":
        raise HTTPException(409, "Only draft campaigns can be activated")

    now = datetime.now(timezone.utc)

    if sale.ends_at <= now:
        raise HTTPException(400, "Campaign has already ended")

    if sale.starts_at > now:
        sale.status = "scheduled"
    else:
        sale.status = "active"

    db.commit()
    db.refresh(sale)

    return sale


# ADD PRODUCT TO CAMPAIGN AND RESERVE STOCK
@router.post(
    "/{sale_id}/products",
    response_model=FlashSaleProductOut,
    status_code=201,
    dependencies=[Depends(require_roles("admin", "operator"))],
)
def add_flash_sale_product(
    sale_id: int,
    data: FlashSaleProductCreate,
    db: Session = Depends(get_db)
):
    try:
        sale = db.scalar(
            select(FlashSale)
            .where(FlashSale.id == sale_id)
            .with_for_update()
        )

        if not sale:
            raise HTTPException(404, "Flash sale not found")

        now = datetime.now(timezone.utc)

        if sale.status not in ("draft", "scheduled") or sale.starts_at <= now:
            raise HTTPException(
                409, "Products can only be allocated before the campaign starts"
            )

        product = db.get(Product, data.product_id)

        if not product or not product.is_active:
            raise HTTPException(404, "Active product not found")

        inventory = db.scalar(
            select(Inventory)
            .where(Inventory.product_id == data.product_id)
            .with_for_update()
        )

        if not inventory:
            raise HTTPException(404, "Product inventory not found")

        available = inventory.quantity - inventory.reserved_quantity

        if data.allocated_quantity > available:
            raise HTTPException(
                409,
                f"Insufficient available stock. Available: {available}"
            )

        listing = FlashSaleProduct(
            flash_sale_id=sale_id,
            product_id=data.product_id,
            sale_price=data.sale_price,
            allocated_quantity=data.allocated_quantity,
            sold_quantity=0
        )

        inventory.reserved_quantity += data.allocated_quantity

        db.add(listing)
        db.flush()
        db.commit()
        db.refresh(listing)

        return listing

    except HTTPException:
        db.rollback()
        raise
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            409, "Product is already allocated to this campaign"
        )


# LIST PRODUCTS IN A CAMPAIGN
@router.get(
    "/{sale_id}/products",
    response_model=list[FlashSaleProductOut],
    dependencies=[Depends(require_roles("admin", "analyst", "operator"))],
)
def list_flash_sale_products(
    sale_id: int,
    db: Session = Depends(get_db)
):
    if not db.get(FlashSale, sale_id):
        raise HTTPException(404, "Flash sale not found")

    return db.scalars(
        select(FlashSaleProduct)
        .where(FlashSaleProduct.flash_sale_id == sale_id)
        .order_by(FlashSaleProduct.id)
    ).all()
