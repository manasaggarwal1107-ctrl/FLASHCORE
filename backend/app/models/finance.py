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


class PaymentApprovalPolicy(Base):
    __tablename__ = "payment_approval_policies"

    __table_args__ = (
        UniqueConstraint(
            "organisation_id", name="uq_payment_approval_policies_org_id"
        ),
        CheckConstraint(
            "refund_approval_threshold_minor >= 0",
            name="chk_payment_approval_policies_threshold",
        ),
    )

    id: Mapped[int] = mapped_column(
        BigInteger, Identity(always=True), primary_key=True
    )
    organisation_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("organisations.id"), nullable=False
    )
    refund_approval_threshold_minor: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default=text("100000")
    )
    currency: Mapped[str] = mapped_column(
        String(3), nullable=False, server_default=text("'INR'")
    )
    updated_by_user_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("users.id")
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("NOW()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("NOW()"),
        onupdate=func.now(),
    )


class PaymentRefund(Base):
    __tablename__ = "payment_refunds"

    __table_args__ = (
        CheckConstraint("amount_minor > 0", name="chk_payment_refunds_amount"),
        CheckConstraint(
            "refund_type IN ('FULL', 'PARTIAL')",
            name="chk_payment_refunds_type",
        ),
        CheckConstraint(
            "status IN ('REQUESTED', 'APPROVAL_PENDING', 'SUBMITTED', 'PENDING', 'PROCESSED', 'FAILED', 'REJECTED')",
            name="chk_payment_refunds_status",
        ),
        Index(
            "uq_payment_refunds_provider_refund_id",
            "provider",
            "provider_refund_id",
            unique=True,
            postgresql_where=text("provider_refund_id IS NOT NULL"),
        ),
        Index(
            "uq_payment_refunds_org_idempotency",
            "organisation_id",
            "idempotency_key",
            unique=True,
            postgresql_where=text("idempotency_key IS NOT NULL"),
        ),
        Index("idx_payment_refunds_org_id", "organisation_id"),
        Index("idx_payment_refunds_txn_id", "payment_transaction_id"),
        Index("idx_payment_refunds_order_id", "order_id"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger, Identity(always=True), primary_key=True
    )
    organisation_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("organisations.id"), nullable=False
    )
    order_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("orders.id"), nullable=False
    )
    payment_order_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("payment_orders.id"), nullable=False
    )
    payment_transaction_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("payment_transactions.id"), nullable=False
    )
    payment_attempt_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("payment_attempts.id")
    )
    provider: Mapped[str] = mapped_column(String(30), nullable=False)
    provider_payment_id: Mapped[str] = mapped_column(String(120), nullable=False)
    provider_refund_id: Mapped[str | None] = mapped_column(String(120))
    idempotency_key: Mapped[str | None] = mapped_column(String(128))
    amount_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(
        String(3), nullable=False, server_default=text("'INR'")
    )
    refund_type: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, server_default=text("'REQUESTED'")
    )
    reason: Mapped[str | None] = mapped_column(Text)
    notes_json: Mapped[dict | None] = mapped_column("notes", JSONB)
    provider_status: Mapped[str | None] = mapped_column(String(40))
    provider_payload: Mapped[dict | None] = mapped_column(JSONB)
    failure_code: Mapped[str | None] = mapped_column(String(80))
    failure_reason: Mapped[str | None] = mapped_column(Text)
    requested_by_user_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("users.id")
    )
    approved_by_user_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("users.id")
    )
    rejected_by_user_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("users.id")
    )
    submitted_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    processed_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("NOW()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("NOW()"),
        onupdate=func.now(),
    )


class PaymentApprovalRequest(Base):
    __tablename__ = "payment_approval_requests"

    __table_args__ = (
        UniqueConstraint("refund_id", name="uq_payment_approval_requests_refund_id"),
        CheckConstraint("amount_minor > 0", name="chk_payment_approval_requests_amount"),
        CheckConstraint(
            "threshold_minor >= 0",
            name="chk_payment_approval_requests_threshold",
        ),
        CheckConstraint(
            "request_type IN ('HIGH_VALUE_REFUND')",
            name="chk_payment_approval_requests_type",
        ),
        CheckConstraint(
            "status IN ('PENDING', 'APPROVED', 'REJECTED', 'CONSUMED')",
            name="chk_payment_approval_requests_status",
        ),
        Index("idx_payment_approval_requests_org_id", "organisation_id"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger, Identity(always=True), primary_key=True
    )
    organisation_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("organisations.id"), nullable=False
    )
    refund_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("payment_refunds.id", ondelete="CASCADE"), nullable=False
    )
    order_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("orders.id"), nullable=False
    )
    payment_transaction_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("payment_transactions.id"), nullable=False
    )
    request_type: Mapped[str] = mapped_column(
        String(30), nullable=False, server_default=text("'HIGH_VALUE_REFUND'")
    )
    amount_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    threshold_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'PENDING'")
    )
    requested_by_user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id"), nullable=False
    )
    decided_by_user_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("users.id")
    )
    decision_note: Mapped[str | None] = mapped_column(Text)
    decided_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("NOW()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("NOW()"),
        onupdate=func.now(),
    )


class PaymentRefundEvent(Base):
    __tablename__ = "payment_refund_events"

    __table_args__ = (
        CheckConstraint(
            "source IN ('api', 'approval', 'provider_sync', 'webhook')",
            name="chk_payment_refund_events_source",
        ),
        Index("idx_payment_refund_events_org_id", "organisation_id"),
        Index("idx_payment_refund_events_refund_id", "refund_id"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger, Identity(always=True), primary_key=True
    )
    organisation_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("organisations.id"), nullable=False
    )
    refund_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("payment_refunds.id", ondelete="CASCADE"), nullable=False
    )
    from_status: Mapped[str | None] = mapped_column(String(30))
    to_status: Mapped[str] = mapped_column(String(30), nullable=False)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    source: Mapped[str] = mapped_column(String(30), nullable=False)
    actor_ref: Mapped[str | None] = mapped_column(String(150))
    details: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("NOW()")
    )


class PaymentLink(Base):
    __tablename__ = "payment_links"

    __table_args__ = (
        UniqueConstraint(
            "provider", "provider_link_id", name="uq_payment_links_provider_link_id"
        ),
        UniqueConstraint(
            "organisation_id", "reference_id", name="uq_payment_links_org_reference"
        ),
        Index(
            "uq_payment_links_org_idempotency",
            "organisation_id",
            "idempotency_key",
            unique=True,
            postgresql_where=text("idempotency_key IS NOT NULL"),
        ),
        CheckConstraint("amount_minor > 0", name="chk_payment_links_amount"),
        CheckConstraint(
            "amount_paid_minor >= 0", name="chk_payment_links_amount_paid"
        ),
        CheckConstraint(
            "status IN ('CREATED', 'ACTIVE', 'PARTIALLY_PAID', 'PAID', 'EXPIRED', 'CANCELLED', 'FAILED')",
            name="chk_payment_links_status",
        ),
        Index("idx_payment_links_org_id", "organisation_id"),
        Index("idx_payment_links_order_id", "order_id"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger, Identity(always=True), primary_key=True
    )
    organisation_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("organisations.id"), nullable=False
    )
    order_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("orders.id"), nullable=False
    )
    customer_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("customers.id")
    )
    provider_account_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("payment_provider_accounts.id"), nullable=False
    )
    provider: Mapped[str] = mapped_column(String(30), nullable=False)
    provider_link_id: Mapped[str] = mapped_column(String(120), nullable=False)
    reference_id: Mapped[str] = mapped_column(String(80), nullable=False)
    idempotency_key: Mapped[str | None] = mapped_column(String(128))
    amount_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    amount_paid_minor: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default=text("0")
    )
    currency: Mapped[str] = mapped_column(
        String(3), nullable=False, server_default=text("'INR'")
    )
    accept_partial: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("FALSE")
    )
    description: Mapped[str | None] = mapped_column(Text)
    customer_name: Mapped[str | None] = mapped_column(String(150))
    customer_email: Mapped[str | None] = mapped_column(String(320))
    customer_phone: Mapped[str | None] = mapped_column(String(30))
    short_url: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'CREATED'")
    )
    expires_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    paid_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    cancelled_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    provider_payload: Mapped[dict | None] = mapped_column(JSONB)
    created_by_user_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("users.id")
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("NOW()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("NOW()"),
        onupdate=func.now(),
    )


class PaymentStatementImport(Base):
    __tablename__ = "payment_statement_imports"

    __table_args__ = (
        UniqueConstraint(
            "organisation_id",
            "file_hash",
            name="uq_payment_statement_imports_org_hash",
        ),
        CheckConstraint(
            "file_size_bytes >= 0", name="chk_payment_statement_imports_size"
        ),
        CheckConstraint("row_count >= 0", name="chk_payment_statement_imports_rows"),
        CheckConstraint(
            "status IN ('IMPORTED', 'FAILED')",
            name="chk_payment_statement_imports_status",
        ),
        Index("idx_payment_statement_imports_org_id", "organisation_id"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger, Identity(always=True), primary_key=True
    )
    organisation_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("organisations.id"), nullable=False
    )
    provider: Mapped[str] = mapped_column(String(30), nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    row_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'IMPORTED'")
    )
    error_message: Mapped[str | None] = mapped_column(Text)
    raw_summary: Mapped[dict | None] = mapped_column(JSONB)
    imported_by_user_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("users.id")
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("NOW()")
    )


class PaymentSettlement(Base):
    __tablename__ = "payment_settlements"

    __table_args__ = (
        UniqueConstraint(
            "organisation_id",
            "provider",
            "provider_settlement_id",
            name="uq_payment_settlements_org_prov_sid",
        ),
        CheckConstraint(
            "gross_amount_minor >= 0", name="chk_payment_settlements_gross"
        ),
        CheckConstraint(
            "refund_amount_minor >= 0", name="chk_payment_settlements_refund"
        ),
        CheckConstraint("fee_minor >= 0", name="chk_payment_settlements_fee"),
        CheckConstraint("tax_minor >= 0", name="chk_payment_settlements_tax"),
        CheckConstraint(
            "status IN ('INITIATED', 'PROCESSED', 'FAILED', 'REVERSED', 'UNAVAILABLE')",
            name="chk_payment_settlements_status",
        ),
        CheckConstraint(
            "source IN ('provider_sync', 'statement_import')",
            name="chk_payment_settlements_source",
        ),
        Index("idx_payment_settlements_org_id", "organisation_id"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger, Identity(always=True), primary_key=True
    )
    organisation_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("organisations.id"), nullable=False
    )
    provider_account_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("payment_provider_accounts.id")
    )
    statement_import_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("payment_statement_imports.id")
    )
    provider: Mapped[str] = mapped_column(String(30), nullable=False)
    provider_settlement_id: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    gross_amount_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    refund_amount_minor: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default=text("0")
    )
    fee_minor: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default=text("0")
    )
    tax_minor: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default=text("0")
    )
    adjustment_minor: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default=text("0")
    )
    net_amount_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(
        String(3), nullable=False, server_default=text("'INR'")
    )
    settlement_utr: Mapped[str | None] = mapped_column(String(120))
    period_start: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    period_end: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    settled_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    source: Mapped[str] = mapped_column(String(30), nullable=False)
    raw_metadata: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("NOW()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("NOW()"),
        onupdate=func.now(),
    )


class PaymentSettlementItem(Base):
    __tablename__ = "payment_settlement_items"

    __table_args__ = (
        CheckConstraint(
            "entity_type IN ('PAYMENT', 'REFUND', 'FEE', 'ADJUSTMENT')",
            name="chk_payment_settlement_items_type",
        ),
        Index("idx_payment_settlement_items_org_id", "organisation_id"),
        Index("idx_payment_settlement_items_settlement_id", "settlement_id"),
        Index("idx_payment_settlement_items_txn_id", "payment_transaction_id"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger, Identity(always=True), primary_key=True
    )
    organisation_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("organisations.id"), nullable=False
    )
    settlement_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("payment_settlements.id", ondelete="CASCADE"),
        nullable=False,
    )
    payment_transaction_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("payment_transactions.id")
    )
    refund_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("payment_refunds.id")
    )
    order_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("orders.id")
    )
    entity_type: Mapped[str] = mapped_column(String(20), nullable=False)
    provider_entity_id: Mapped[str | None] = mapped_column(String(120))
    gross_amount_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    fee_minor: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default=text("0")
    )
    tax_minor: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default=text("0")
    )
    net_amount_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(
        String(3), nullable=False, server_default=text("'INR'")
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("NOW()")
    )


class PaymentReconciliationRun(Base):
    __tablename__ = "payment_reconciliation_runs"

    __table_args__ = (
        UniqueConstraint(
            "organisation_id",
            "run_reference",
            name="uq_payment_recon_runs_org_ref",
        ),
        CheckConstraint(
            "status IN ('RUNNING', 'COMPLETED', 'FAILED')",
            name="chk_payment_recon_runs_status",
        ),
        Index("idx_payment_recon_runs_org_id", "organisation_id"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger, Identity(always=True), primary_key=True
    )
    organisation_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("organisations.id"), nullable=False
    )
    run_reference: Mapped[str] = mapped_column(String(80), nullable=False)
    provider: Mapped[str] = mapped_column(String(30), nullable=False)
    currency: Mapped[str] = mapped_column(
        String(3), nullable=False, server_default=text("'INR'")
    )
    period_start: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    period_end: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'RUNNING'")
    )
    total_checked: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    matched_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    exception_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    summary_json: Mapped[dict | None] = mapped_column(JSONB)
    triggered_by_user_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("users.id")
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("NOW()")
    )
    completed_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))


class PaymentReconciliationItem(Base):
    __tablename__ = "payment_reconciliation_items"

    __table_args__ = (
        CheckConstraint(
            "outcome IN ('MATCHED', 'MISSING_IN_PROVIDER', 'MISSING_IN_FLASHCORE', 'AMOUNT_MISMATCH', 'CURRENCY_MISMATCH', 'STATUS_MISMATCH', 'REFUND_MISMATCH', 'SETTLEMENT_MISMATCH', 'DUPLICATE', 'NEEDS_REVIEW')",
            name="chk_payment_recon_items_outcome",
        ),
        CheckConstraint(
            "entity_type IN ('PAYMENT', 'REFUND', 'SETTLEMENT', 'ORDER')",
            name="chk_payment_recon_items_entity_type",
        ),
        CheckConstraint(
            "resolution_status IN ('UNRESOLVED', 'ACKNOWLEDGED', 'RESOLVED')",
            name="chk_payment_recon_items_resolution",
        ),
        Index("idx_payment_recon_items_org_id", "organisation_id"),
        Index("idx_payment_recon_items_run_id", "run_id"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger, Identity(always=True), primary_key=True
    )
    organisation_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("organisations.id"), nullable=False
    )
    run_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("payment_reconciliation_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    outcome: Mapped[str] = mapped_column(String(40), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(30), nullable=False)
    order_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("orders.id")
    )
    payment_transaction_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("payment_transactions.id")
    )
    refund_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("payment_refunds.id")
    )
    settlement_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("payment_settlements.id")
    )
    provider_ref: Mapped[str | None] = mapped_column(String(120))
    expected_amount_minor: Mapped[int | None] = mapped_column(BigInteger)
    actual_amount_minor: Mapped[int | None] = mapped_column(BigInteger)
    expected_currency: Mapped[str | None] = mapped_column(String(3))
    actual_currency: Mapped[str | None] = mapped_column(String(3))
    expected_status: Mapped[str | None] = mapped_column(String(40))
    actual_status: Mapped[str | None] = mapped_column(String(40))
    discrepancy_details: Mapped[dict | None] = mapped_column(JSONB)
    resolution_status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'UNRESOLVED'")
    )
    resolution_note: Mapped[str | None] = mapped_column(Text)
    resolved_by_user_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("users.id")
    )
    resolved_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("NOW()")
    )
