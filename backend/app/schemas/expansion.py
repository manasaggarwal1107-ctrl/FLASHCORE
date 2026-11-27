from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


# ---- Stage 6: Warehouses, Transfers, Suppliers, Purchase Orders, Intelligence ----


class WarehouseCreate(BaseModel):
    code: str = Field(min_length=1, max_length=60)
    name: str = Field(min_length=1, max_length=150)
    location_type: Literal["warehouse", "store", "fulfilment_centre"] = "warehouse"
    address: str | None = None
    city: str | None = Field(default=None, max_length=100)
    state: str | None = Field(default=None, max_length=100)
    postal_code: str | None = Field(default=None, max_length=30)
    is_default: bool = False
    is_active: bool = True


class WarehouseOut(BaseModel):
    id: str
    organisation_id: int
    code: str
    name: str
    location_type: str
    address: str | None = None
    city: str | None = None
    state: str | None = None
    postal_code: str | None = None
    is_default: bool
    is_active: bool
    total_units: int = 0
    reserved_units: int = 0
    damaged_units: int = 0
    created_at: datetime


class DamagedStockAdjustRequest(BaseModel):
    product_id: int = Field(gt=0)
    location_id: int = Field(gt=0)
    quantity_delta: int
    reason: str = Field(min_length=1, max_length=300)


class StockTransferCreate(BaseModel):
    product_id: int = Field(gt=0)
    from_location_id: int = Field(gt=0)
    to_location_id: int = Field(gt=0)
    quantity: int = Field(gt=0, le=100000)
    requires_approval: bool = False
    notes: str | None = Field(default=None, max_length=500)


class StockTransferOut(BaseModel):
    id: str
    transfer_number: str
    organisation_id: int
    product_id: str
    product_name: str
    sku: str
    from_location_id: int
    from_location_name: str
    to_location_id: int
    to_location_name: str
    quantity: int
    status: str
    requires_approval: bool
    notes: str | None = None
    requested_by: str
    approved_by: str | None = None
    dispatched_at: datetime | None = None
    received_at: datetime | None = None
    created_at: datetime


class SupplierCreate(BaseModel):
    code: str = Field(min_length=1, max_length=60)
    name: str = Field(min_length=1, max_length=180)
    contact_name: str | None = Field(default=None, max_length=150)
    email: str | None = Field(default=None, max_length=320)
    phone: str | None = Field(default=None, max_length=40)
    gstin: str | None = Field(default=None, max_length=20)
    state_code: str | None = Field(default=None, max_length=4)
    address: str | None = None
    payment_terms: str | None = Field(default=None, max_length=120)
    status: Literal["active", "inactive"] = "active"


class SupplierOut(BaseModel):
    id: str
    organisation_id: int
    code: str
    name: str
    contact_name: str | None = None
    email: str | None = None
    phone: str | None = None
    gstin: str | None = None
    state_code: str | None = None
    outstanding_payable_minor: int = 0
    outstanding_payable: str = "0.00"
    address: str | None = None
    payment_terms: str | None = None
    status: str
    order_count: int = 0
    total_spend_minor: int = 0
    total_spend: str = "0.00"
    created_at: datetime


class PurchaseOrderItemIn(BaseModel):
    product_id: int = Field(gt=0)
    ordered_quantity: int = Field(gt=0, le=100000)
    unit_cost_minor: int = Field(ge=0)


class PurchaseOrderCreate(BaseModel):
    supplier_id: int = Field(gt=0)
    location_id: int = Field(gt=0)
    expected_at: datetime | None = None
    notes: str | None = Field(default=None, max_length=500)
    items: list[PurchaseOrderItemIn] = Field(min_length=1, max_length=100)


class PurchaseOrderReceiveItemIn(BaseModel):
    item_id: int = Field(gt=0)
    quantity_received: int = Field(gt=0, le=100000)


class PurchaseOrderReceiveRequest(BaseModel):
    items: list[PurchaseOrderReceiveItemIn] = Field(min_length=1)
    note: str | None = Field(default=None, max_length=300)


class PurchaseOrderItemOut(BaseModel):
    id: str
    product_id: str
    sku: str
    product_name: str
    ordered_quantity: int
    received_quantity: int
    unit_cost_minor: int
    unit_cost: str
    line_total_minor: int
    line_total: str


class PurchaseOrderOut(BaseModel):
    id: str
    organisation_id: int
    po_number: str
    supplier_id: str
    supplier_name: str
    location_id: int
    location_name: str
    status: str
    currency: str
    total_cost_minor: int
    total_cost: str
    expected_at: datetime | None = None
    submitted_at: datetime | None = None
    received_at: datetime | None = None
    notes: str | None = None
    created_by: str
    items: list[PurchaseOrderItemOut]
    created_at: datetime


class InventoryIntelligenceItemOut(BaseModel):
    product_id: str
    sku: str
    product_name: str
    on_hand: int
    reserved: int
    available: int
    damaged: int
    reorder_threshold: int
    units_sold_30d: int
    suggested_reorder_qty: int
    classification: str
    days_since_movement: int | None = None
    stock_value_minor: int
    stock_value: str


class InventoryIntelligenceOut(BaseModel):
    total_stock_value_minor: int
    total_stock_value: str
    low_stock_count: int
    out_of_stock_count: int
    dead_stock_count: int
    insufficient_data: bool
    note: str | None = None
    items: list[InventoryIntelligenceItemOut]


# ---- Stage 7: Surge Campaigns & Promotions ----


class CampaignProductIn(BaseModel):
    product_id: int = Field(gt=0)
    allocated_units: int = Field(gt=0, le=100000)
    sale_price_minor: int | None = Field(default=None, ge=0)


class SurgeCampaignCreate(BaseModel):
    name: str = Field(min_length=1, max_length=180)
    description: str | None = Field(default=None, max_length=600)
    starts_at: datetime
    ends_at: datetime
    discount_type: Literal["percentage", "fixed"] = "percentage"
    discount_value: int = Field(gt=0)
    category_filter: str | None = Field(default=None, max_length=120)
    campaign_limit_units: int | None = Field(default=None, gt=0)
    per_customer_limit: int | None = Field(default=None, gt=0)
    activate_immediately: bool = False
    products: list[CampaignProductIn] = Field(min_length=1, max_length=100)


class SurgeCampaignTransition(BaseModel):
    target_status: Literal["SCHEDULED", "ACTIVE", "PAUSED", "COMPLETED", "CANCELLED"]


class CampaignProductOut(BaseModel):
    id: str
    product_id: str
    sku: str
    product_name: str
    original_price_minor: int
    original_price: str
    sale_price_minor: int
    sale_price: str
    allocated_units: int
    sold_units: int
    remaining_units: int


class SurgeCampaignOut(BaseModel):
    id: str
    organisation_id: int
    name: str
    description: str | None = None
    status: str
    starts_at: datetime
    ends_at: datetime
    discount_type: str
    discount_value: int
    category_filter: str | None = None
    campaign_limit_units: int | None = None
    total_units_sold: int
    per_customer_limit: int | None = None
    revenue_minor: int = 0
    revenue: str = "0.00"
    orders_generated: int = 0
    products: list[CampaignProductOut]
    created_by: str
    created_at: datetime


class PromotionCreate(BaseModel):
    code: str = Field(min_length=2, max_length=60)
    name: str = Field(min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=400)
    discount_type: Literal["percentage", "fixed"] = "percentage"
    discount_value: int = Field(gt=0)
    min_order_minor: int = Field(default=0, ge=0)
    max_discount_minor: int | None = Field(default=None, ge=0)
    usage_limit: int | None = Field(default=None, gt=0)
    per_customer_limit: int | None = Field(default=None, gt=0)
    customer_id: int | None = Field(default=None, gt=0)
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    is_active: bool = True


class PromotionOut(BaseModel):
    id: str
    organisation_id: int
    code: str
    name: str
    description: str | None = None
    discount_type: str
    discount_value: int
    min_order_minor: int
    min_order: str
    max_discount_minor: int | None = None
    max_discount: str | None = None
    usage_limit: int | None = None
    used_count: int
    per_customer_limit: int | None = None
    customer_id: int | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    is_active: bool
    created_at: datetime


class CouponValidateRequest(BaseModel):
    code: str = Field(min_length=1, max_length=60)
    subtotal_minor: int = Field(ge=0)
    customer_id: int | None = Field(default=None, gt=0)


class CouponValidateOut(BaseModel):
    valid: bool
    code: str
    discount_minor: int
    discount: str
    reason: str | None = None


# ---- Stage 8 & Operations: Sales Records, Dashboard, Returns, Alerts, Voice ----


class SalesRecordOut(BaseModel):
    id: str
    organisation_id: int
    transaction_ref: str
    order_id: str
    order_number: str
    customer_id: int | None = None
    customer_name: str | None = None
    location_id: int | None = None
    campaign_id: int | None = None
    gross_amount_minor: int
    gross_amount: str
    discount_minor: int
    discount: str
    tax_minor: int
    tax: str
    net_amount_minor: int
    net_amount: str
    refunded_minor: int
    refunded: str
    currency: str
    payment_status: str
    refund_status: str
    sold_at: datetime


class SalesDashboardOut(BaseModel):
    today_sales_minor: int
    today_sales: str
    total_revenue_minor: int
    total_revenue: str
    net_revenue_after_refunds_minor: int
    net_revenue_after_refunds: str
    order_count: int
    average_order_value_minor: int
    average_order_value: str
    previous_period_revenue_minor: int
    previous_period_revenue: str
    revenue_delta_percent: float | None = None
    top_products: list[dict[str, Any]]
    slow_products: list[dict[str, Any]]
    sales_by_category: list[dict[str, Any]]
    sales_by_location: list[dict[str, Any]]
    trend: list[dict[str, Any]]
    recent_transactions: list[SalesRecordOut]
    repeat_customer_rate_percent: float | None = None
    inventory_turnover_ratio: float | None = None
    top_sku_concentration_percent: float | None = None


class ReturnItemIn(BaseModel):
    order_item_id: int = Field(gt=0)
    quantity: int = Field(gt=0)
    condition: Literal["unopened", "good", "damaged", "defective"] = "good"


class ReturnCreate(BaseModel):
    order_id: int = Field(gt=0)
    return_type: Literal["return", "exchange"] = "return"
    reason: str = Field(min_length=3, max_length=500)
    items: list[ReturnItemIn] = Field(min_length=1)


class ReturnReviewRequest(BaseModel):
    decision: Literal["APPROVED", "REJECTED", "COMPLETED"]
    restock_approved: bool = False
    trigger_refund: bool = False
    create_exchange_order: bool = False
    note: str | None = Field(default=None, max_length=300)


class ReturnItemOut(BaseModel):
    id: str
    order_item_id: int
    product_id: str
    product_name: str
    sku: str
    quantity: int
    condition: str
    restocked: bool


class ReturnOut(BaseModel):
    id: str
    organisation_id: int
    return_number: str
    order_id: str
    order_number: str
    customer_id: int | None = None
    return_type: str
    status: str
    reason: str
    condition: str
    restock_approved: bool
    refund_amount_minor: int
    refund_amount: str
    refund_id: str | None = None
    exchange_order_id: str | None = None
    requested_by: str
    reviewed_by: str | None = None
    items: list[ReturnItemOut]
    created_at: datetime


class NotificationOut(BaseModel):
    id: str
    category: str
    severity: str
    title: str
    message: str
    entity_type: str | None = None
    entity_id: str | None = None
    is_read: bool
    read_at: datetime | None = None
    created_at: datetime


class VoiceSessionCreate(BaseModel):
    language_mode: Literal["en", "hi", "hinglish", "auto"] = "auto"
    title: str | None = Field(default=None, max_length=200)


class VoiceQueryRequest(BaseModel):
    session_id: int | None = None
    transcript: str = Field(min_length=1, max_length=2000)
    language: Literal["en", "hi", "hinglish", "auto"] = "auto"
    input_mode: Literal["voice", "text"] = "text"


class AiActionProposalOut(BaseModel):
    id: str
    tool_name: str
    arguments: dict[str, Any]
    summary: str
    status: str
    approved_by: str | None = None
    result: dict[str, Any] | None = None
    error_message: str | None = None
    created_at: datetime


class AiActionDecisionRequest(BaseModel):
    approve: bool
    note: str | None = Field(default=None, max_length=300)


class VoiceMessageOut(BaseModel):
    id: str
    role: str
    content: str
    transcript_language: str | None = None
    tool_calls: list[dict[str, Any]] | dict[str, Any] | None = None
    created_at: datetime


class VoiceSessionOut(BaseModel):
    id: str
    language_mode: str
    title: str
    messages: list[VoiceMessageOut] = []
    proposals: list[AiActionProposalOut] = []
    created_at: datetime


class VoiceQueryResponse(BaseModel):
    session_id: str
    reply: str
    language: str
    provider: str
    model: str
    tool_executions: list[dict[str, Any]] = []
    pending_proposal: AiActionProposalOut | None = None
    tts_hint: dict[str, Any]
