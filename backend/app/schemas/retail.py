from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


def format_minor_to_decimal_str(amount_minor: int) -> str:
    value = (Decimal(amount_minor) / Decimal(100)).quantize(Decimal("0.01"))
    return f"{value:.2f}"


class InventorySummaryOut(BaseModel):
    on_hand: int
    reserved: int
    sold: int
    available: int
    low_stock_threshold: int | None = None


class CommerceProductCreate(BaseModel):
    sku: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=200)
    description: str | None = None
    category: str | None = Field(default=None, max_length=120)
    status: Literal["draft", "active", "archived"] = "active"
    price_minor: int = Field(ge=0)
    currency: str = Field(default="INR", min_length=3, max_length=3)
    tax_rate_bps: int = Field(default=0, ge=0, le=10000)
    metadata: dict | None = None

    @field_validator("sku", "name")
    @classmethod
    def strip_required(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Field cannot be blank.")
        return cleaned

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        cleaned = value.strip().upper()
        if len(cleaned) != 3 or not cleaned.isalpha():
            raise ValueError("Currency must be a 3-letter ISO-4217 code.")
        return cleaned


class CommerceProductUpdate(BaseModel):
    sku: str | None = Field(default=None, min_length=1, max_length=80)
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    category: str | None = Field(default=None, max_length=120)
    status: Literal["draft", "active", "archived"] | None = None
    price_minor: int | None = Field(default=None, ge=0)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    tax_rate_bps: int | None = Field(default=None, ge=0, le=10000)
    metadata: dict | None = None

    @field_validator("sku", "name")
    @classmethod
    def strip_optional(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Field cannot be blank.")
        return cleaned

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip().upper()
        if len(cleaned) != 3 or not cleaned.isalpha():
            raise ValueError("Currency must be a 3-letter ISO-4217 code.")
        return cleaned


class CommerceProductOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    organisation_id: int
    sku: str
    name: str
    description: str | None = None
    category: str | None = None
    status: str
    price_minor: int
    price: str
    currency: str
    tax_rate_bps: int
    metadata: dict | None = None
    inventory: InventorySummaryOut
    origin: str = "real"
    source: str = "manual"
    created_at: datetime
    updated_at: datetime


class CommerceProductListResponse(BaseModel):
    items: list[CommerceProductOut]
    total: int
    page: int
    page_size: int


class InventoryLocationCreate(BaseModel):
    code: str = Field(min_length=1, max_length=60)
    name: str = Field(min_length=1, max_length=150)
    location_type: Literal["warehouse", "store", "fulfilment_centre"] = "warehouse"
    is_active: bool = True

    @field_validator("code", "name")
    @classmethod
    def strip_loc(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Field cannot be blank.")
        return cleaned


class InventoryLocationOut(BaseModel):
    id: int
    organisation_id: int
    code: str
    name: str
    location_type: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


class InventoryAdjustmentCreate(BaseModel):
    product_id: int = Field(gt=0)
    location_id: int | None = Field(default=None, gt=0)
    quantity_delta: int
    low_stock_threshold: int | None = Field(default=None, ge=0)
    reason: str = Field(min_length=3, max_length=500)


class InventoryBalanceOut(BaseModel):
    id: int
    product_id: str
    sku: str
    product_name: str
    location_id: int
    location_code: str
    location_name: str
    on_hand: int
    reserved: int
    available: int
    low_stock_threshold: int
    origin: str = "real"
    updated_at: datetime


class InventoryBalanceListResponse(BaseModel):
    items: list[InventoryBalanceOut]
    total: int
    page: int
    page_size: int


class InventoryMovementOut(BaseModel):
    id: str
    balance_id: int
    product_id: str
    sku: str
    product_name: str
    location_id: int
    location_name: str
    type: str
    quantity_delta: int
    reserved_delta: int
    balance_after: int
    reserved_after: int
    reference_type: str | None = None
    reference_id: str | None = None
    reason: str | None = None
    actor: str | None = None
    origin: str = "real"
    occurred_at: datetime


class InventoryMovementListResponse(BaseModel):
    items: list[InventoryMovementOut]
    total: int
    page: int
    page_size: int


class CustomerCreate(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    email: str | None = Field(default=None, min_length=5, max_length=320)
    phone: str | None = Field(default=None, max_length=30)
    billing_address: dict | None = None
    shipping_address: dict | None = None

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Customer name cannot be blank.")
        return cleaned

    @field_validator("email")
    @classmethod
    def clean_email(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip().lower()
        return cleaned or None


class CustomerOut(BaseModel):
    id: str
    organisation_id: int
    reference: str
    name: str
    email: str | None = None
    phone: str | None = None
    billing_address: dict | None = None
    shipping_address: dict | None = None
    status: str
    order_count: int = 0
    origin: str = "real"
    created_at: datetime
    updated_at: datetime


class CustomerListResponse(BaseModel):
    items: list[CustomerOut]
    total: int
    page: int
    page_size: int


class OrderItemCreate(BaseModel):
    product_id: int = Field(gt=0)
    location_id: int | None = Field(default=None, gt=0)
    quantity: int = Field(gt=0, le=100000)


class OrderCreate(BaseModel):
    customer_id: int | None = Field(default=None, gt=0)
    items: list[OrderItemCreate] = Field(min_length=1, max_length=100)
    discount_minor: int = Field(default=0, ge=0)
    submit_for_payment: bool = True
    reservation_ttl_minutes: int = Field(default=15, ge=1, le=1440)


class OrderTransitionRequest(BaseModel):
    target_status: Literal["PENDING_PAYMENT", "PROCESSING", "FULFILLED", "CANCELLED"]
    reason: str | None = Field(default=None, max_length=500)


class OrderLineOut(BaseModel):
    id: int
    product_id: str
    location_id: int
    sku: str
    product_name: str
    quantity: int
    unit_price_minor: int
    unit_price: str
    tax_rate_bps: int
    tax_minor: int
    line_total_minor: int
    line_total: str


class OrderEventOut(BaseModel):
    id: int
    from_status: str | None = None
    to_status: str
    event_type: str
    actor_ref: str | None = None
    details: dict | None = None
    created_at: datetime


class OrderOut(BaseModel):
    id: str
    organisation_id: int
    reference: str
    customer_id: int | None = None
    customer_ref: str | None = None
    customer_name: str | None = None
    currency: str
    subtotal_minor: int
    subtotal: str
    discount_minor: int
    discount: str
    tax_minor: int
    tax: str
    total_minor: int
    total: str
    status: str
    payment_status: str
    item_count: int
    lines: list[OrderLineOut]
    events: list[OrderEventOut] | None = None
    reservation_expires_at: datetime | None = None
    transaction_ref: str | None = None
    origin: str = "real"
    placed_at: datetime
    created_at: datetime
    updated_at: datetime


class OrderListResponse(BaseModel):
    items: list[OrderOut]
    total: int
    page: int
    page_size: int
