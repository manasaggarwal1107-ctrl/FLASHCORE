from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class RefundPolicyUpdate(BaseModel):
    refund_approval_threshold_minor: int = Field(ge=0)
    currency: str = Field(default="INR", min_length=3, max_length=3)

    @field_validator("currency")
    @classmethod
    def clean_currency(cls, value: str) -> str:
        c = value.strip().upper()
        if len(c) != 3 or not c.isalpha():
            raise ValueError("Currency must be a 3-letter ISO-4217 code.")
        return c


class RefundPolicyOut(BaseModel):
    organisation_id: int
    refund_approval_threshold_minor: int
    refund_approval_threshold: str
    currency: str
    updated_at: datetime


class RefundCreateRequest(BaseModel):
    amount_minor: int | None = Field(default=None, gt=0)
    reason: str = Field(min_length=3, max_length=500)
    notes: dict[str, str] | None = None


class RefundDecisionRequest(BaseModel):
    decision_note: str | None = Field(default=None, max_length=500)


class RefundEventOut(BaseModel):
    id: int
    from_status: str | None = None
    to_status: str
    event_type: str
    source: str
    actor_ref: str | None = None
    details: dict | None = None
    created_at: datetime


class RefundApprovalOut(BaseModel):
    id: str
    refund_id: str
    order_id: str
    payment_transaction_id: str
    amount_minor: int
    amount: str
    currency: str
    threshold_minor: int
    status: str
    requested_by_user_id: int
    decided_by_user_id: int | None = None
    decision_note: str | None = None
    decided_at: datetime | None = None
    created_at: datetime


class RefundOut(BaseModel):
    id: str
    organisation_id: int
    order_id: str
    payment_order_id: str
    payment_transaction_id: str
    provider: str
    provider_payment_id: str
    provider_refund_id: str | None = None
    amount_minor: int
    amount: str
    currency: str
    refund_type: str
    status: str
    reason: str | None = None
    provider_status: str | None = None
    failure_code: str | None = None
    failure_reason: str | None = None
    requires_approval: bool = False
    approval_request: RefundApprovalOut | None = None
    events: list[RefundEventOut] | None = None
    submitted_at: datetime | None = None
    processed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class RefundListResponse(BaseModel):
    items: list[RefundOut]
    total: int
    page: int
    page_size: int


class PaymentLinkCreateRequest(BaseModel):
    order_id: int = Field(gt=0)
    amount_minor: int | None = Field(default=None, gt=0)
    description: str = Field(min_length=3, max_length=300)
    accept_partial: bool = False
    expires_in_hours: int | None = Field(default=72, ge=1, le=720)
    customer_name: str | None = Field(default=None, max_length=150)
    customer_email: str | None = Field(default=None, max_length=320)
    customer_phone: str | None = Field(default=None, max_length=30)


class PaymentLinkOut(BaseModel):
    id: str
    organisation_id: int
    order_id: str
    customer_id: int | None = None
    provider: str
    provider_link_id: str
    reference_id: str
    amount_minor: int
    amount: str
    amount_paid_minor: int
    amount_paid: str
    currency: str
    accept_partial: bool
    description: str | None = None
    customer_name: str | None = None
    customer_email: str | None = None
    customer_phone: str | None = None
    short_url: str
    status: str
    expires_at: datetime | None = None
    paid_at: datetime | None = None
    cancelled_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class PaymentLinkListResponse(BaseModel):
    items: list[PaymentLinkOut]
    total: int
    page: int
    page_size: int


class SettlementItemOut(BaseModel):
    id: str
    entity_type: str
    provider_entity_id: str | None = None
    payment_transaction_id: str | None = None
    refund_id: str | None = None
    order_id: str | None = None
    gross_amount_minor: int
    gross_amount: str
    fee_minor: int
    fee: str
    tax_minor: int
    tax: str
    net_amount_minor: int
    net_amount: str
    currency: str


class SettlementOut(BaseModel):
    id: str
    organisation_id: int
    provider: str
    provider_settlement_id: str
    status: str
    gross_amount_minor: int
    gross_amount: str
    refund_amount_minor: int
    refund_amount: str
    fee_minor: int
    fee: str
    tax_minor: int
    tax: str
    adjustment_minor: int
    adjustment: str
    net_amount_minor: int
    net_amount: str
    currency: str
    settlement_utr: str | None = None
    period_start: datetime | None = None
    period_end: datetime | None = None
    settled_at: datetime | None = None
    source: str
    items: list[SettlementItemOut] | None = None
    created_at: datetime
    updated_at: datetime


class SettlementListResponse(BaseModel):
    items: list[SettlementOut]
    total: int
    page: int
    page_size: int


class SettlementSyncResponse(BaseModel):
    status: Literal["synced", "capability_unavailable"]
    synced_count: int = 0
    message: str


class SettlementImportResponse(BaseModel):
    import_id: str
    idempotent_replay: bool
    filename: str
    file_hash: str
    row_count: int
    settlements_created: int


class SettlementCsvImportRequest(BaseModel):
    provider: Literal["razorpay"] = "razorpay"
    filename: str = Field(min_length=5, max_length=255)
    csv_content: str = Field(min_length=1, max_length=2_000_000)

    @field_validator("filename")
    @classmethod
    def check_csv_filename(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned.lower().endswith(".csv") or "/" in cleaned or "\\" in cleaned:
            raise ValueError("Statement file must be a valid .csv filename without path separators.")
        return cleaned


class ReconciliationRunCreateRequest(BaseModel):
    provider: Literal["razorpay"] = "razorpay"
    currency: str = Field(default="INR", min_length=3, max_length=3)
    period_start: datetime | None = None
    period_end: datetime | None = None
    include_provider_fetch: bool = False

    @field_validator("currency")
    @classmethod
    def norm_curr(cls, v: str) -> str:
        c = v.strip().upper()
        if len(c) != 3 or not c.isalpha():
            raise ValueError("Currency must be a 3-letter ISO-4217 code.")
        return c


class ReconciliationItemOut(BaseModel):
    id: str
    run_id: str
    outcome: str
    entity_type: str
    order_id: str | None = None
    payment_transaction_id: str | None = None
    refund_id: str | None = None
    settlement_id: str | None = None
    provider_ref: str | None = None
    expected_amount_minor: int | None = None
    actual_amount_minor: int | None = None
    expected_currency: str | None = None
    actual_currency: str | None = None
    expected_status: str | None = None
    actual_status: str | None = None
    discrepancy_details: dict | None = None
    resolution_status: str
    resolution_note: str | None = None
    resolved_by_user_id: int | None = None
    resolved_at: datetime | None = None
    created_at: datetime


class ReconciliationItemListResponse(BaseModel):
    items: list[ReconciliationItemOut]
    total: int
    page: int
    page_size: int


class ReconciliationRunOut(BaseModel):
    id: str
    organisation_id: int
    run_reference: str
    provider: str
    currency: str
    period_start: datetime | None = None
    period_end: datetime | None = None
    status: str
    total_checked: int
    matched_count: int
    exception_count: int
    summary_json: dict | None = None
    created_at: datetime
    completed_at: datetime | None = None


class ReconciliationRunListResponse(BaseModel):
    items: list[ReconciliationRunOut]
    total: int
    page: int
    page_size: int


class ReconciliationResolveRequest(BaseModel):
    resolution_status: Literal["ACKNOWLEDGED", "RESOLVED"] = "RESOLVED"
    resolution_note: str = Field(min_length=3, max_length=500)


class FinanceOverviewOut(BaseModel):
    organisation_id: int
    currency: str
    period_start: datetime | None = None
    period_end: datetime | None = None
    gross_captured_minor: int
    gross_captured: str
    successful_payment_count: int
    failed_payment_count: int
    full_refund_count: int
    partial_refund_count: int
    total_refunded_minor: int
    total_refunded: str
    pending_refund_minor: int
    pending_refund: str
    pending_refund_count: int
    gateway_fees_minor: int
    gateway_fees: str
    gateway_tax_minor: int
    gateway_tax: str
    gross_settlements_minor: int
    gross_settlements: str
    net_settlements_minor: int
    net_settlements: str
    unsettled_captured_minor: int
    unsettled_captured: str
    reconciliation_exceptions_count: int
    active_payment_links_count: int
    paid_payment_links_count: int
    calculation_notes: dict[str, str]
