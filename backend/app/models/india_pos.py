from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    ForeignKey,
    Identity,
    Index,
    Integer,
    String,
    Text,
    TIMESTAMP,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class OrgTaxProfile(Base):
    __tablename__ = "org_tax_profiles"

    __table_args__ = (
        UniqueConstraint(
            "organisation_id",
            name="uq_org_tax_profiles_org_id",
        ),
        CheckConstraint(
            "registration_type IN ('regular', 'composition', 'unregistered')",
            name="chk_org_tax_profiles_reg_type",
        ),
        CheckConstraint(
            "dpdp_retention_days >= 30",
            name="chk_org_tax_profiles_retention",
        ),
    )

    id: Mapped[int] = mapped_column(
        BigInteger, Identity(always=True), primary_key=True
    )
    organisation_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("organisations.id"), nullable=False
    )
    legal_name: Mapped[str] = mapped_column(String(200), nullable=False)
    gstin: Mapped[str | None] = mapped_column(String(20))
    registration_type: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'regular'")
    )
    state_name: Mapped[str] = mapped_column(
        String(80), nullable=False, server_default=text("'Maharashtra'")
    )
    state_code: Mapped[str] = mapped_column(
        String(4), nullable=False, server_default=text("'27'")
    )
    address: Mapped[str | None] = mapped_column(Text)
    invoice_prefix: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default=text("'INV'")
    )
    financial_year_code: Mapped[str] = mapped_column(
        String(12), nullable=False, server_default=text("'2627'")
    )
    tax_inclusive_default: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("FALSE")
    )
    allow_negative_stock: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("FALSE")
    )
    dpdp_retention_days: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("1095")
    )
    e_invoice_provider: Mapped[str | None] = mapped_column(String(60))
    e_way_provider: Mapped[str | None] = mapped_column(String(60))
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("NOW()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("NOW()"),
        onupdate=func.now(),
    )


class Invoice(Base):
    __tablename__ = "invoices"

    __table_args__ = (
        UniqueConstraint(
            "organisation_id",
            "invoice_number",
            name="uq_invoices_org_number",
        ),
        CheckConstraint(
            "document_type IN ('tax_invoice', 'bill_of_supply', 'credit_note', 'debit_note')",
            name="chk_invoices_doc_type",
        ),
        CheckConstraint(
            "status IN ('ISSUED', 'VOID')",
            name="chk_invoices_status",
        ),
        Index("idx_invoices_org_id", "organisation_id"),
        Index("idx_invoices_order_id", "order_id"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger, Identity(always=True), primary_key=True
    )
    organisation_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("organisations.id"), nullable=False
    )
    invoice_number: Mapped[str] = mapped_column(String(60), nullable=False)
    document_type: Mapped[str] = mapped_column(
        String(24), nullable=False, server_default=text("'tax_invoice'")
    )
    financial_year: Mapped[str] = mapped_column(String(12), nullable=False)
    order_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("orders.id"))
    return_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("order_returns.id")
    )
    customer_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("customers.id")
    )
    customer_name: Mapped[str | None] = mapped_column(String(150))
    customer_gstin: Mapped[str | None] = mapped_column(String(20))
    supplier_gstin: Mapped[str | None] = mapped_column(String(20))
    place_of_supply_state: Mapped[str] = mapped_column(String(4), nullable=False)
    is_interstate: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("FALSE")
    )
    taxable_value_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    discount_minor: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default=text("0")
    )
    cgst_minor: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default=text("0")
    )
    sgst_minor: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default=text("0")
    )
    igst_minor: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default=text("0")
    )
    total_tax_minor: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default=text("0")
    )
    total_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'ISSUED'")
    )
    irn_status: Mapped[str] = mapped_column(
        String(30), nullable=False, server_default=text("'ADAPTER_READY'")
    )
    line_items_snapshot: Mapped[list | dict] = mapped_column(JSONB, nullable=False)
    issued_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("NOW()")
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("NOW()")
    )


class PosShift(Base):
    __tablename__ = "pos_shifts"

    __table_args__ = (
        CheckConstraint("status IN ('OPEN', 'CLOSED')", name="chk_pos_shifts_status"),
        CheckConstraint("opening_cash_minor >= 0", name="chk_pos_shifts_opening"),
        Index("idx_pos_shifts_org_id", "organisation_id"),
        Index("idx_pos_shifts_org_status", "organisation_id", "status"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger, Identity(always=True), primary_key=True
    )
    organisation_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("organisations.id"), nullable=False
    )
    location_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("inventory_locations.id"), nullable=False
    )
    cashier_user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id"), nullable=False
    )
    cashier_email: Mapped[str] = mapped_column(String(150), nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default=text("'OPEN'")
    )
    opening_cash_minor: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default=text("0")
    )
    cash_sales_minor: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default=text("0")
    )
    upi_sales_minor: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default=text("0")
    )
    card_sales_minor: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default=text("0")
    )
    bank_sales_minor: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default=text("0")
    )
    expected_cash_minor: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default=text("0")
    )
    counted_cash_minor: Mapped[int | None] = mapped_column(BigInteger)
    variance_minor: Mapped[int | None] = mapped_column(BigInteger)
    notes: Mapped[str | None] = mapped_column(Text)
    opened_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("NOW()")
    )
    closed_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))


class PosHeldBill(Base):
    __tablename__ = "pos_held_bills"

    __table_args__ = (
        CheckConstraint(
            "status IN ('HELD', 'RESUMED', 'DISCARDED')",
            name="chk_pos_held_bills_status",
        ),
        Index("idx_pos_held_bills_org_id", "organisation_id"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger, Identity(always=True), primary_key=True
    )
    organisation_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("organisations.id"), nullable=False
    )
    location_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("inventory_locations.id"), nullable=False
    )
    cashier_email: Mapped[str] = mapped_column(String(150), nullable=False)
    label: Mapped[str] = mapped_column(String(120), nullable=False)
    customer_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("customers.id")
    )
    coupon_code: Mapped[str | None] = mapped_column(String(60))
    discount_minor: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default=text("0")
    )
    items_json: Mapped[list] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'HELD'")
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("NOW()")
    )


class OrderPaymentSplit(Base):
    __tablename__ = "order_payment_splits"

    __table_args__ = (
        CheckConstraint(
            "method IN ('cash', 'upi', 'card', 'bank_transfer', 'razorpay', 'store_credit')",
            name="chk_order_payment_splits_method",
        ),
        CheckConstraint("amount_minor > 0", name="chk_order_payment_splits_amount"),
        Index("idx_order_payment_splits_org_id", "organisation_id"),
        Index("idx_order_payment_splits_order_id", "order_id"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger, Identity(always=True), primary_key=True
    )
    organisation_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("organisations.id"), nullable=False
    )
    order_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False
    )
    method: Mapped[str] = mapped_column(String(30), nullable=False)
    amount_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    reference_utr: Mapped[str | None] = mapped_column(String(120))
    verified: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("TRUE")
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("NOW()")
    )


class PurchaseRequisition(Base):
    __tablename__ = "purchase_requisitions"

    __table_args__ = (
        UniqueConstraint(
            "organisation_id",
            "req_number",
            name="uq_purchase_requisitions_org_number",
        ),
        CheckConstraint(
            "status IN ('DRAFT', 'PENDING_APPROVAL', 'APPROVED', 'REJECTED', 'CONVERTED_TO_PO')",
            name="chk_purchase_requisitions_status",
        ),
        Index("idx_purchase_requisitions_org_id", "organisation_id"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger, Identity(always=True), primary_key=True
    )
    organisation_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("organisations.id"), nullable=False
    )
    req_number: Mapped[str] = mapped_column(String(60), nullable=False)
    location_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("inventory_locations.id"), nullable=False
    )
    supplier_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("suppliers.id")
    )
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, server_default=text("'PENDING_APPROVAL'")
    )
    items_json: Mapped[list] = mapped_column(JSONB, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    requested_by: Mapped[str] = mapped_column(String(150), nullable=False)
    approved_by: Mapped[str | None] = mapped_column(String(150))
    purchase_order_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("purchase_orders.id")
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("NOW()")
    )


class SupplierInvoice(Base):
    __tablename__ = "supplier_invoices"

    __table_args__ = (
        UniqueConstraint(
            "organisation_id",
            "invoice_number",
            name="uq_supplier_invoices_org_number",
        ),
        CheckConstraint(
            "status IN ('UNPAID', 'PARTIALLY_PAID', 'PAID')",
            name="chk_supplier_invoices_status",
        ),
        CheckConstraint(
            "total_minor >= 0 AND paid_minor >= 0",
            name="chk_supplier_invoices_amounts",
        ),
        Index("idx_supplier_invoices_org_id", "organisation_id"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger, Identity(always=True), primary_key=True
    )
    organisation_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("organisations.id"), nullable=False
    )
    invoice_number: Mapped[str] = mapped_column(String(80), nullable=False)
    supplier_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("suppliers.id"), nullable=False
    )
    purchase_order_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("purchase_orders.id"), nullable=False
    )
    subtotal_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    gst_minor: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default=text("0")
    )
    total_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    paid_minor: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default=text("0")
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'UNPAID'")
    )
    issued_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("NOW()")
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("NOW()")
    )


class LoyaltyLedger(Base):
    __tablename__ = "loyalty_ledger"

    __table_args__ = (
        CheckConstraint(
            "entry_type IN ('EARN', 'REDEEM', 'ADJUST', 'CREDIT_ISSUE', 'CREDIT_USE')",
            name="chk_loyalty_ledger_type",
        ),
        Index("idx_loyalty_ledger_org_cust", "organisation_id", "customer_id"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger, Identity(always=True), primary_key=True
    )
    organisation_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("organisations.id"), nullable=False
    )
    customer_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("customers.id", ondelete="CASCADE"), nullable=False
    )
    order_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("orders.id"))
    entry_type: Mapped[str] = mapped_column(String(24), nullable=False)
    points_delta: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    store_credit_delta_minor: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default=text("0")
    )
    reason: Mapped[str] = mapped_column(String(240), nullable=False)
    actor_ref: Mapped[str | None] = mapped_column(String(150))
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("NOW()")
    )


class AutomationRule(Base):
    __tablename__ = "automation_rules"

    __table_args__ = (
        CheckConstraint(
            "trigger_type IN ('low_stock', 'campaign_expiry', 'pending_po', 'refund_spike', 'unreceived_transfer', 'reconciliation_mismatch')",
            name="chk_automation_rules_trigger",
        ),
        Index("idx_automation_rules_org_id", "organisation_id"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger, Identity(always=True), primary_key=True
    )
    organisation_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("organisations.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    trigger_type: Mapped[str] = mapped_column(String(40), nullable=False)
    threshold_value: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("5")
    )
    action_type: Mapped[str] = mapped_column(
        String(40), nullable=False, server_default=text("'in_app_alert'")
    )
    is_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("TRUE")
    )
    last_run_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    last_status: Mapped[str | None] = mapped_column(String(40))
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("NOW()")
    )
