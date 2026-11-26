from pydantic import BaseModel, Field, ConfigDict
from decimal import Decimal


class CategoryCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    parent_id: int | None = None


class CategoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    parent_id: int | None


class ProductCreate(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    sku: str = Field(min_length=2, max_length=80)
    description: str | None = None
    category_id: int | None = None
    price: Decimal = Field(ge=0, max_digits=12, decimal_places=2)


class ProductOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    sku: str
    description: str | None
    category_id: int | None
    price: Decimal
    currency: str
    origin: str
    is_active: bool


class InventoryCreate(BaseModel):
    product_id: int
    quantity: int = Field(ge=0)
    low_stock_threshold: int = Field(default=5, ge=0)


class InventoryUpdate(BaseModel):
    quantity: int = Field(ge=0)


class InventoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    product_id: int
    quantity: int
    reserved_quantity: int
    low_stock_threshold: int