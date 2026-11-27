from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class OrgTaxProfileUpsert(BaseModel):
    legal_name: str = Field(min_length=2, max_length=200)
    gstin: str | None = Field(default=None, max_length=20)
    registration_type: Literal["regular", "composition", "unregistered"] = "regular"
    state_name: str = Field(default="Maharashtra", min_length=2, max_length=80)
    state_code: str = Field(default="27", min_length=2, max_length=4)
    address: str | None = None
    invoice_prefix: str = Field(default="INV", min_length=1, max_length=16)
    financial_year_code: str = Field(default="2627", min_length=2, max_length=12)
    tax_inclusive_default: bool = False
    allow_negative_stock: bool = False
    dpdp_retention_days: int = Field(default=1095, ge=30, le=3650)
    e_invoice_provider: str | None = Field(default=None, max_length=60)
    e_way_provider: str | None = Field(default=None, max_length=60)


class OrgTaxProfileOut(BaseModel):
    id: str
    organisation_id: int
    legal_name: str
    gstin: str | None = None
    registration_type: str
    state_name: str
    state_code: str
    address: str | None = None
    invoice_prefix: str
    financial_year_code: str
    tax_inclusive_default: bool
    allow_negative_stock: bool
    dpdp_retention_days: int
    e_invoice_provider: str | None = None
    e_way_provider: str | None = None
    updated_at: datetime


class InvoiceOut(BaseModel):
    id: str
    organisation_id: int
    invoice_number: str
    document_type: str
    financial_year: str
    order_id: str | None = None
    return_id: str | None = None
    customer_id: int | None = None
    customer_name: str | None = None
    customer_gstin: str | None = None
    supplier_gstin: str | None = None
    place_of_supply_state: str
    is_interstate: bool
    taxable_value_minor: int
    taxable_value: str
    discount_minor: int
    discount: str
    cgst_minor: int
    cgst: str
    sgst_minor: int
    sgst: str
    igst_minor: int
    igst: str
    total_tax_minor: int
    total_tax: str
    total_minor: int
    total: str
    status: str
    irn_status: str
    line_items_snapshot: list[dict[str, Any]] | dict[str, Any]
    issued_at: datetime


class PosShiftOpenRequest(BaseModel):
    location_id: int = Field(gt=0)
    opening_cash_minor: int = Field(default=0, ge=0)
    notes: str | None = Field(default=None, max_length=300)


class PosShiftCloseRequest(BaseModel):
    counted_cash_minor: int = Field(ge=0)
    notes: str | None = Field(default=None, max_length=300)


class PosShiftOut(BaseModel):
    id: str
    organisation_id: int
    location_id: int
    location_name: str
    cashier_email: str
    status: str
    opening_cash_minor: int
    opening_cash: str
    cash_sales_minor: int
    cash_sales: str
    upi_sales_minor: int
    upi_sales: str
    card_sales_minor: int
    card_sales: str
    bank_sales_minor: int
    bank_sales: str
    expected_cash_minor: int
    expected_cash: str
    counted_cash_minor: int | None = None
    counted_cash: str | None = None
    variance_minor: int | None = None
    variance: str | None = None
    opened_at: datetime
    closed_at: datetime | None = None


class PosCartItemIn(BaseModel):
    product_id: int = Field(gt=0)
    quantity: int = Field(gt=0, le=100000)
    unit_multiplier: int = Field(default=1, ge=1, le=1000)
    item_discount_minor: int = Field(default=0, ge=0)


class PosPaymentSplitIn(BaseModel):
    method: Literal["cash", "upi", "card", "bank_transfer", "razorpay", "store_credit"]
    amount_minor: int = Field(gt=0)
    reference_utr: str | None = Field(default=None, max_length=120)


class PosCheckoutRequest(BaseModel):
    location_id: int = Field(gt=0)
    customer_id: int | None = Field(default=None, gt=0)
    shift_id: int | None = Field(default=None, gt=0)
    held_bill_id: int | None = Field(default=None, gt=0)
    campaign_id: int | None = Field(default=None, gt=0)
    coupon_code: str | None = Field(default=None, max_length=60)
    bill_discount_minor: int = Field(default=0, ge=0)
    place_of_supply_state: str | None = Field(default=None, min_length=2, max_length=4)
    offline_tx_id: str | None = Field(default=None, max_length=100)
    items: list[PosCartItemIn] = Field(min_length=1, max_length=100)
    payments: list[PosPaymentSplitIn] = Field(min_length=1, max_length=10)


class PosHeldBillCreate(BaseModel):
    location_id: int = Field(gt=0)
    label: str = Field(min_length=1, max_length=120)
    customer_id: int | None = Field(default=None, gt=0)
    coupon_code: str | None = Field(default=None, max_length=60)
    discount_minor: int = Field(default=0, ge=0)
    items: list[PosCartItemIn] = Field(min_length=1)


class PosHeldBillOut(BaseModel):
    id: str
    location_id: int
    cashier_email: str
    label: str
    customer_id: int | None = None
    coupon_code: str | None = None
    discount_minor: int
    items: list[dict[str, Any]]
    status: str
    created_at: datetime


class PosCheckoutOut(BaseModel):
    order_id: str
    order_number: str
    order_status: str
    payment_status: str
    invoice: InvoiceOut | None = None
    subtotal_minor: int
    discount_minor: int
    cgst_minor: int
    sgst_minor: int
    igst_minor: int
    total_minor: int
    total: str
    payments: list[dict[str, Any]]
    offline_replayed: bool = False


class StockCountItemIn(BaseModel):
    product_id: int = Field(gt=0)
    counted_quantity: int = Field(ge=0)
    note: str | None = Field(default=None, max_length=200)


class StockCountRequest(BaseModel):
    location_id: int = Field(gt=0)
    items: list[StockCountItemIn] = Field(min_length=1, max_length=200)


class RequisitionCreate(BaseModel):
    location_id: int = Field(gt=0)
    supplier_id: int | None = Field(default=None, gt=0)
    notes: str | None = Field(default=None, max_length=400)
    items: list[dict[str, Any]] = Field(min_length=1)


class SupplierInvoiceCreate(BaseModel):
    invoice_number: str = Field(min_length=2, max_length=80)
    supplier_id: int = Field(gt=0)
    purchase_order_id: int = Field(gt=0)
    subtotal_minor: int = Field(ge=0)
    gst_minor: int = Field(default=0, ge=0)


class SupplierPaymentRequest(BaseModel):
    amount_minor: int = Field(gt=0)


class CustomerConsentUpdate(BaseModel):
    marketing_consent: bool
    opt_out: bool = False


class LoyaltyAdjustRequest(BaseModel):
    points_delta: int = 0
    store_credit_delta_minor: int = 0
    reason: str = Field(min_length=2, max_length=240)


class AutomationRuleCreate(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    trigger_type: Literal[
        "low_stock",
        "campaign_expiry",
        "pending_po",
        "refund_spike",
        "unreceived_transfer",
        "reconciliation_mismatch",
    ]
    threshold_value: int = Field(default=5, ge=0)
    is_enabled: bool = True
