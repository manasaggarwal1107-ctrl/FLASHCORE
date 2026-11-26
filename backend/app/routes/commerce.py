from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core.database import get_db
from app.core.auth_dependencies import require_roles
from app.models.commerce import Category, Product, Inventory
from app.schemas.commerce import (
    CategoryCreate, CategoryOut,
    ProductCreate, ProductOut,
    InventoryCreate, InventoryUpdate, InventoryOut
)

router = APIRouter(prefix="/api", tags=["Commerce"])


# ---------------- CATEGORIES ----------------

@router.post("/categories", response_model=CategoryOut, status_code=201, dependencies=[Depends(require_roles("admin", "operator"))])
def create_category(data: CategoryCreate, db: Session = Depends(get_db)):
    category = Category(**data.model_dump())
    db.add(category)

    try:
        db.commit()
        db.refresh(category)
        return category
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Category already exists or parent is invalid")


@router.get("/categories", response_model=list[CategoryOut], dependencies=[Depends(require_roles("admin", "analyst", "operator"))])
def list_categories(db: Session = Depends(get_db)):
    return db.scalars(
        select(Category).order_by(Category.id)
    ).all()


# ---------------- PRODUCTS ----------------

@router.post("/products", response_model=ProductOut, status_code=201, dependencies=[Depends(require_roles("admin", "operator"))])
def create_product(data: ProductCreate, db: Session = Depends(get_db)):
    product = Product(**data.model_dump())
    db.add(product)

    try:
        db.commit()
        db.refresh(product)
        return product
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            409, "Product SKU already exists or category is invalid"
        )


@router.get("/products", response_model=list[ProductOut], dependencies=[Depends(require_roles("admin", "analyst", "operator"))])
def list_products(db: Session = Depends(get_db)):
    return db.scalars(
        select(Product).order_by(Product.id)
    ).all()


@router.get("/products/{product_id}", response_model=ProductOut, dependencies=[Depends(require_roles("admin", "analyst", "operator"))])
def get_product(product_id: int, db: Session = Depends(get_db)):
    product = db.get(Product, product_id)

    if not product:
        raise HTTPException(404, "Product not found")

    return product


# ---------------- INVENTORY ----------------

@router.post("/inventory", response_model=InventoryOut, status_code=201, dependencies=[Depends(require_roles("admin", "operator"))])
def create_inventory(data: InventoryCreate, db: Session = Depends(get_db)):
    if not db.get(Product, data.product_id):
        raise HTTPException(404, "Product not found")

    inventory = Inventory(**data.model_dump())
    db.add(inventory)

    try:
        db.commit()
        db.refresh(inventory)
        return inventory
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Inventory already exists for this product")


@router.get("/inventory", response_model=list[InventoryOut], dependencies=[Depends(require_roles("admin", "analyst", "operator"))])
def list_inventory(db: Session = Depends(get_db)):
    return db.scalars(
        select(Inventory).order_by(Inventory.id)
    ).all()


@router.patch("/inventory/{product_id}", response_model=InventoryOut, dependencies=[Depends(require_roles("admin", "operator"))])
def update_inventory(
    product_id: int,
    data: InventoryUpdate,
    db: Session = Depends(get_db)
):
    inventory = db.scalar(
        select(Inventory).where(Inventory.product_id == product_id)
    )

    if not inventory:
        raise HTTPException(404, "Inventory record not found")

    if data.quantity < inventory.reserved_quantity:
        raise HTTPException(
            400, "Quantity cannot be lower than reserved stock"
        )

    inventory.quantity = data.quantity

    try:
        db.commit()
        db.refresh(inventory)
        return inventory
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Inventory update failed")


@router.get("/inventory/low-stock", response_model=list[InventoryOut], dependencies=[Depends(require_roles("admin", "analyst", "operator"))])
def low_stock_inventory(db: Session = Depends(get_db)):
    return db.scalars(
        select(Inventory).where(
            Inventory.quantity - Inventory.reserved_quantity
            <= Inventory.low_stock_threshold
        )
    ).all()