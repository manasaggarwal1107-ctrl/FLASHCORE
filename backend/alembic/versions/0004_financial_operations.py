"""Add Stage 4 financial operations tables (refunds, approvals, links, settlements, reconciliation).

Revision ID: 0004_financial_operations
Revises: 0003_commerce_and_payments
Create Date: 2026-11-27 10:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0004_financial_operations"
down_revision: Union[str, None] = "0003_commerce_and_payments"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "payment_approval_policies",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("organisation_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "refund_approval_threshold_minor",
            sa.BigInteger(),
            server_default=sa.text("100000"),
            nullable=False,
        ),
        sa.Column(
            "currency",
            sa.String(length=3),
            server_default=sa.text("'INR'"),
            nullable=False,
        ),
        sa.Column("updated_by_user_id", sa.BigInteger(), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "refund_approval_threshold_minor >= 0",
            name="chk_payment_approval_policies_threshold",
        ),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"]),
        sa.ForeignKeyConstraint(["updated_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organisation_id", name="uq_payment_approval_policies_org_id"
        ),
    )

    op.create_table(
        "payment_refunds",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("organisation_id", sa.BigInteger(), nullable=False),
        sa.Column("order_id", sa.BigInteger(), nullable=False),
        sa.Column("payment_order_id", sa.BigInteger(), nullable=False),
        sa.Column("payment_transaction_id", sa.BigInteger(), nullable=False),
        sa.Column("payment_attempt_id", sa.BigInteger(), nullable=True),
        sa.Column("provider", sa.String(length=30), nullable=False),
        sa.Column("provider_payment_id", sa.String(length=120), nullable=False),
        sa.Column("provider_refund_id", sa.String(length=120), nullable=True),
        sa.Column("idempotency_key", sa.String(length=128), nullable=True),
        sa.Column("amount_minor", sa.BigInteger(), nullable=False),
        sa.Column(
            "currency",
            sa.String(length=3),
            server_default=sa.text("'INR'"),
            nullable=False,
        ),
        sa.Column("refund_type", sa.String(length=20), nullable=False),
        sa.Column(
            "status",
            sa.String(length=30),
            server_default=sa.text("'REQUESTED'"),
            nullable=False,
        ),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("notes", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("provider_status", sa.String(length=40), nullable=True),
        sa.Column(
            "provider_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
        sa.Column("failure_code", sa.String(length=80), nullable=True),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column("requested_by_user_id", sa.BigInteger(), nullable=True),
        sa.Column("approved_by_user_id", sa.BigInteger(), nullable=True),
        sa.Column("rejected_by_user_id", sa.BigInteger(), nullable=True),
        sa.Column("submitted_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("processed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.CheckConstraint("amount_minor > 0", name="chk_payment_refunds_amount"),
        sa.CheckConstraint(
            "refund_type IN ('FULL', 'PARTIAL')", name="chk_payment_refunds_type"
        ),
        sa.CheckConstraint(
            "status IN ('REQUESTED', 'APPROVAL_PENDING', 'SUBMITTED', 'PENDING', 'PROCESSED', 'FAILED', 'REJECTED')",
            name="chk_payment_refunds_status",
        ),
        sa.ForeignKeyConstraint(["approved_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"]),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"]),
        sa.ForeignKeyConstraint(["payment_attempt_id"], ["payment_attempts.id"]),
        sa.ForeignKeyConstraint(["payment_order_id"], ["payment_orders.id"]),
        sa.ForeignKeyConstraint(
            ["payment_transaction_id"], ["payment_transactions.id"]
        ),
        sa.ForeignKeyConstraint(["rejected_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["requested_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_payment_refunds_org_id", "payment_refunds", ["organisation_id"])
    op.create_index(
        "idx_payment_refunds_txn_id", "payment_refunds", ["payment_transaction_id"]
    )
    op.create_index("idx_payment_refunds_order_id", "payment_refunds", ["order_id"])
    op.create_index(
        "uq_payment_refunds_provider_refund_id",
        "payment_refunds",
        ["provider", "provider_refund_id"],
        unique=True,
        postgresql_where=sa.text("provider_refund_id IS NOT NULL"),
    )
    op.create_index(
        "uq_payment_refunds_org_idempotency",
        "payment_refunds",
        ["organisation_id", "idempotency_key"],
        unique=True,
        postgresql_where=sa.text("idempotency_key IS NOT NULL"),
    )

    op.create_table(
        "payment_approval_requests",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("organisation_id", sa.BigInteger(), nullable=False),
        sa.Column("refund_id", sa.BigInteger(), nullable=False),
        sa.Column("order_id", sa.BigInteger(), nullable=False),
        sa.Column("payment_transaction_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "request_type",
            sa.String(length=30),
            server_default=sa.text("'HIGH_VALUE_REFUND'"),
            nullable=False,
        ),
        sa.Column("amount_minor", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("threshold_minor", sa.BigInteger(), nullable=False),
        sa.Column(
            "status",
            sa.String(length=20),
            server_default=sa.text("'PENDING'"),
            nullable=False,
        ),
        sa.Column("requested_by_user_id", sa.BigInteger(), nullable=False),
        sa.Column("decided_by_user_id", sa.BigInteger(), nullable=True),
        sa.Column("decision_note", sa.Text(), nullable=True),
        sa.Column("decided_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "amount_minor > 0", name="chk_payment_approval_requests_amount"
        ),
        sa.CheckConstraint(
            "threshold_minor >= 0",
            name="chk_payment_approval_requests_threshold",
        ),
        sa.CheckConstraint(
            "request_type IN ('HIGH_VALUE_REFUND')",
            name="chk_payment_approval_requests_type",
        ),
        sa.CheckConstraint(
            "status IN ('PENDING', 'APPROVED', 'REJECTED', 'CONSUMED')",
            name="chk_payment_approval_requests_status",
        ),
        sa.ForeignKeyConstraint(["decided_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"]),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"]),
        sa.ForeignKeyConstraint(
            ["payment_transaction_id"], ["payment_transactions.id"]
        ),
        sa.ForeignKeyConstraint(
            ["refund_id"], ["payment_refunds.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["requested_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("refund_id", name="uq_payment_approval_requests_refund_id"),
    )
    op.create_index(
        "idx_payment_approval_requests_org_id",
        "payment_approval_requests",
        ["organisation_id"],
    )

    op.create_table(
        "payment_refund_events",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("organisation_id", sa.BigInteger(), nullable=False),
        sa.Column("refund_id", sa.BigInteger(), nullable=False),
        sa.Column("from_status", sa.String(length=30), nullable=True),
        sa.Column("to_status", sa.String(length=30), nullable=False),
        sa.Column("event_type", sa.String(length=50), nullable=False),
        sa.Column("source", sa.String(length=30), nullable=False),
        sa.Column("actor_ref", sa.String(length=150), nullable=True),
        sa.Column("details", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "source IN ('api', 'approval', 'provider_sync', 'webhook')",
            name="chk_payment_refund_events_source",
        ),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"]),
        sa.ForeignKeyConstraint(
            ["refund_id"], ["payment_refunds.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_payment_refund_events_org_id",
        "payment_refund_events",
        ["organisation_id"],
    )
    op.create_index(
        "idx_payment_refund_events_refund_id",
        "payment_refund_events",
        ["refund_id"],
    )

    op.create_table(
        "payment_links",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("organisation_id", sa.BigInteger(), nullable=False),
        sa.Column("order_id", sa.BigInteger(), nullable=False),
        sa.Column("customer_id", sa.BigInteger(), nullable=True),
        sa.Column("provider_account_id", sa.BigInteger(), nullable=False),
        sa.Column("provider", sa.String(length=30), nullable=False),
        sa.Column("provider_link_id", sa.String(length=120), nullable=False),
        sa.Column("reference_id", sa.String(length=80), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=True),
        sa.Column("amount_minor", sa.BigInteger(), nullable=False),
        sa.Column(
            "amount_paid_minor",
            sa.BigInteger(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "currency",
            sa.String(length=3),
            server_default=sa.text("'INR'"),
            nullable=False,
        ),
        sa.Column(
            "accept_partial",
            sa.Boolean(),
            server_default=sa.text("FALSE"),
            nullable=False,
        ),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("customer_name", sa.String(length=150), nullable=True),
        sa.Column("customer_email", sa.String(length=320), nullable=True),
        sa.Column("customer_phone", sa.String(length=30), nullable=True),
        sa.Column("short_url", sa.Text(), nullable=False),
        sa.Column(
            "status",
            sa.String(length=20),
            server_default=sa.text("'CREATED'"),
            nullable=False,
        ),
        sa.Column("expires_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("paid_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "provider_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
        sa.Column("created_by_user_id", sa.BigInteger(), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.CheckConstraint("amount_minor > 0", name="chk_payment_links_amount"),
        sa.CheckConstraint(
            "amount_paid_minor >= 0", name="chk_payment_links_amount_paid"
        ),
        sa.CheckConstraint(
            "status IN ('CREATED', 'ACTIVE', 'PARTIALLY_PAID', 'PAID', 'EXPIRED', 'CANCELLED', 'FAILED')",
            name="chk_payment_links_status",
        ),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"]),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"]),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"]),
        sa.ForeignKeyConstraint(
            ["provider_account_id"], ["payment_provider_accounts.id"]
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organisation_id", "reference_id", name="uq_payment_links_org_reference"
        ),
        sa.UniqueConstraint(
            "provider", "provider_link_id", name="uq_payment_links_provider_link_id"
        ),
    )
    op.create_index("idx_payment_links_org_id", "payment_links", ["organisation_id"])
    op.create_index("idx_payment_links_order_id", "payment_links", ["order_id"])
    op.create_index(
        "uq_payment_links_org_idempotency",
        "payment_links",
        ["organisation_id", "idempotency_key"],
        unique=True,
        postgresql_where=sa.text("idempotency_key IS NOT NULL"),
    )

    op.create_table(
        "payment_statement_imports",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("organisation_id", sa.BigInteger(), nullable=False),
        sa.Column("provider", sa.String(length=30), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("file_hash", sa.String(length=64), nullable=False),
        sa.Column("file_size_bytes", sa.Integer(), nullable=False),
        sa.Column(
            "row_count", sa.Integer(), server_default=sa.text("0"), nullable=False
        ),
        sa.Column(
            "status",
            sa.String(length=20),
            server_default=sa.text("'IMPORTED'"),
            nullable=False,
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("raw_summary", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("imported_by_user_id", sa.BigInteger(), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "file_size_bytes >= 0", name="chk_payment_statement_imports_size"
        ),
        sa.CheckConstraint("row_count >= 0", name="chk_payment_statement_imports_rows"),
        sa.CheckConstraint(
            "status IN ('IMPORTED', 'FAILED')",
            name="chk_payment_statement_imports_status",
        ),
        sa.ForeignKeyConstraint(["imported_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organisation_id",
            "file_hash",
            name="uq_payment_statement_imports_org_hash",
        ),
    )
    op.create_index(
        "idx_payment_statement_imports_org_id",
        "payment_statement_imports",
        ["organisation_id"],
    )

    op.create_table(
        "payment_settlements",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("organisation_id", sa.BigInteger(), nullable=False),
        sa.Column("provider_account_id", sa.BigInteger(), nullable=True),
        sa.Column("statement_import_id", sa.BigInteger(), nullable=True),
        sa.Column("provider", sa.String(length=30), nullable=False),
        sa.Column("provider_settlement_id", sa.String(length=120), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("gross_amount_minor", sa.BigInteger(), nullable=False),
        sa.Column(
            "refund_amount_minor",
            sa.BigInteger(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "fee_minor", sa.BigInteger(), server_default=sa.text("0"), nullable=False
        ),
        sa.Column(
            "tax_minor", sa.BigInteger(), server_default=sa.text("0"), nullable=False
        ),
        sa.Column(
            "adjustment_minor",
            sa.BigInteger(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column("net_amount_minor", sa.BigInteger(), nullable=False),
        sa.Column(
            "currency",
            sa.String(length=3),
            server_default=sa.text("'INR'"),
            nullable=False,
        ),
        sa.Column("settlement_utr", sa.String(length=120), nullable=True),
        sa.Column("period_start", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("period_end", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("settled_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("source", sa.String(length=30), nullable=False),
        sa.Column("raw_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "gross_amount_minor >= 0", name="chk_payment_settlements_gross"
        ),
        sa.CheckConstraint(
            "refund_amount_minor >= 0", name="chk_payment_settlements_refund"
        ),
        sa.CheckConstraint("fee_minor >= 0", name="chk_payment_settlements_fee"),
        sa.CheckConstraint("tax_minor >= 0", name="chk_payment_settlements_tax"),
        sa.CheckConstraint(
            "status IN ('INITIATED', 'PROCESSED', 'FAILED', 'REVERSED', 'UNAVAILABLE')",
            name="chk_payment_settlements_status",
        ),
        sa.CheckConstraint(
            "source IN ('provider_sync', 'statement_import')",
            name="chk_payment_settlements_source",
        ),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"]),
        sa.ForeignKeyConstraint(
            ["provider_account_id"], ["payment_provider_accounts.id"]
        ),
        sa.ForeignKeyConstraint(
            ["statement_import_id"], ["payment_statement_imports.id"]
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organisation_id",
            "provider",
            "provider_settlement_id",
            name="uq_payment_settlements_org_prov_sid",
        ),
    )
    op.create_index(
        "idx_payment_settlements_org_id", "payment_settlements", ["organisation_id"]
    )

    op.create_table(
        "payment_settlement_items",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("organisation_id", sa.BigInteger(), nullable=False),
        sa.Column("settlement_id", sa.BigInteger(), nullable=False),
        sa.Column("payment_transaction_id", sa.BigInteger(), nullable=True),
        sa.Column("refund_id", sa.BigInteger(), nullable=True),
        sa.Column("order_id", sa.BigInteger(), nullable=True),
        sa.Column("entity_type", sa.String(length=20), nullable=False),
        sa.Column("provider_entity_id", sa.String(length=120), nullable=True),
        sa.Column("gross_amount_minor", sa.BigInteger(), nullable=False),
        sa.Column(
            "fee_minor", sa.BigInteger(), server_default=sa.text("0"), nullable=False
        ),
        sa.Column(
            "tax_minor", sa.BigInteger(), server_default=sa.text("0"), nullable=False
        ),
        sa.Column("net_amount_minor", sa.BigInteger(), nullable=False),
        sa.Column(
            "currency",
            sa.String(length=3),
            server_default=sa.text("'INR'"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "entity_type IN ('PAYMENT', 'REFUND', 'FEE', 'ADJUSTMENT')",
            name="chk_payment_settlement_items_type",
        ),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"]),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"]),
        sa.ForeignKeyConstraint(
            ["payment_transaction_id"], ["payment_transactions.id"]
        ),
        sa.ForeignKeyConstraint(["refund_id"], ["payment_refunds.id"]),
        sa.ForeignKeyConstraint(
            ["settlement_id"], ["payment_settlements.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_payment_settlement_items_org_id",
        "payment_settlement_items",
        ["organisation_id"],
    )
    op.create_index(
        "idx_payment_settlement_items_settlement_id",
        "payment_settlement_items",
        ["settlement_id"],
    )
    op.create_index(
        "idx_payment_settlement_items_txn_id",
        "payment_settlement_items",
        ["payment_transaction_id"],
    )

    op.create_table(
        "payment_reconciliation_runs",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("organisation_id", sa.BigInteger(), nullable=False),
        sa.Column("run_reference", sa.String(length=80), nullable=False),
        sa.Column("provider", sa.String(length=30), nullable=False),
        sa.Column(
            "currency",
            sa.String(length=3),
            server_default=sa.text("'INR'"),
            nullable=False,
        ),
        sa.Column("period_start", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("period_end", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "status",
            sa.String(length=20),
            server_default=sa.text("'RUNNING'"),
            nullable=False,
        ),
        sa.Column(
            "total_checked", sa.Integer(), server_default=sa.text("0"), nullable=False
        ),
        sa.Column(
            "matched_count", sa.Integer(), server_default=sa.text("0"), nullable=False
        ),
        sa.Column(
            "exception_count", sa.Integer(), server_default=sa.text("0"), nullable=False
        ),
        sa.Column("summary_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("triggered_by_user_id", sa.BigInteger(), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.Column("completed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('RUNNING', 'COMPLETED', 'FAILED')",
            name="chk_payment_recon_runs_status",
        ),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"]),
        sa.ForeignKeyConstraint(["triggered_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organisation_id", "run_reference", name="uq_payment_recon_runs_org_ref"
        ),
    )
    op.create_index(
        "idx_payment_recon_runs_org_id",
        "payment_reconciliation_runs",
        ["organisation_id"],
    )

    op.create_table(
        "payment_reconciliation_items",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("organisation_id", sa.BigInteger(), nullable=False),
        sa.Column("run_id", sa.BigInteger(), nullable=False),
        sa.Column("outcome", sa.String(length=40), nullable=False),
        sa.Column("entity_type", sa.String(length=30), nullable=False),
        sa.Column("order_id", sa.BigInteger(), nullable=True),
        sa.Column("payment_transaction_id", sa.BigInteger(), nullable=True),
        sa.Column("refund_id", sa.BigInteger(), nullable=True),
        sa.Column("settlement_id", sa.BigInteger(), nullable=True),
        sa.Column("provider_ref", sa.String(length=120), nullable=True),
        sa.Column("expected_amount_minor", sa.BigInteger(), nullable=True),
        sa.Column("actual_amount_minor", sa.BigInteger(), nullable=True),
        sa.Column("expected_currency", sa.String(length=3), nullable=True),
        sa.Column("actual_currency", sa.String(length=3), nullable=True),
        sa.Column("expected_status", sa.String(length=40), nullable=True),
        sa.Column("actual_status", sa.String(length=40), nullable=True),
        sa.Column(
            "discrepancy_details",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column(
            "resolution_status",
            sa.String(length=20),
            server_default=sa.text("'UNRESOLVED'"),
            nullable=False,
        ),
        sa.Column("resolution_note", sa.Text(), nullable=True),
        sa.Column("resolved_by_user_id", sa.BigInteger(), nullable=True),
        sa.Column("resolved_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "outcome IN ('MATCHED', 'MISSING_IN_PROVIDER', 'MISSING_IN_FLASHCORE', 'AMOUNT_MISMATCH', 'CURRENCY_MISMATCH', 'STATUS_MISMATCH', 'REFUND_MISMATCH', 'SETTLEMENT_MISMATCH', 'DUPLICATE', 'NEEDS_REVIEW')",
            name="chk_payment_recon_items_outcome",
        ),
        sa.CheckConstraint(
            "entity_type IN ('PAYMENT', 'REFUND', 'SETTLEMENT', 'ORDER')",
            name="chk_payment_recon_items_entity_type",
        ),
        sa.CheckConstraint(
            "resolution_status IN ('UNRESOLVED', 'ACKNOWLEDGED', 'RESOLVED')",
            name="chk_payment_recon_items_resolution",
        ),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"]),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"]),
        sa.ForeignKeyConstraint(
            ["payment_transaction_id"], ["payment_transactions.id"]
        ),
        sa.ForeignKeyConstraint(["refund_id"], ["payment_refunds.id"]),
        sa.ForeignKeyConstraint(["resolved_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(
            ["run_id"], ["payment_reconciliation_runs.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["settlement_id"], ["payment_settlements.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_payment_recon_items_org_id",
        "payment_reconciliation_items",
        ["organisation_id"],
    )
    op.create_index(
        "idx_payment_recon_items_run_id", "payment_reconciliation_items", ["run_id"]
    )


def downgrade() -> None:
    op.drop_index(
        "idx_payment_recon_items_run_id", table_name="payment_reconciliation_items"
    )
    op.drop_index(
        "idx_payment_recon_items_org_id", table_name="payment_reconciliation_items"
    )
    op.drop_table("payment_reconciliation_items")

    op.drop_index(
        "idx_payment_recon_runs_org_id", table_name="payment_reconciliation_runs"
    )
    op.drop_table("payment_reconciliation_runs")

    op.drop_index(
        "idx_payment_settlement_items_txn_id",
        table_name="payment_settlement_items",
    )
    op.drop_index(
        "idx_payment_settlement_items_settlement_id",
        table_name="payment_settlement_items",
    )
    op.drop_index(
        "idx_payment_settlement_items_org_id",
        table_name="payment_settlement_items",
    )
    op.drop_table("payment_settlement_items")

    op.drop_index("idx_payment_settlements_org_id", table_name="payment_settlements")
    op.drop_table("payment_settlements")

    op.drop_index(
        "idx_payment_statement_imports_org_id",
        table_name="payment_statement_imports",
    )
    op.drop_table("payment_statement_imports")

    op.drop_index("uq_payment_links_org_idempotency", table_name="payment_links")
    op.drop_index("idx_payment_links_order_id", table_name="payment_links")
    op.drop_index("idx_payment_links_org_id", table_name="payment_links")
    op.drop_table("payment_links")

    op.drop_index(
        "idx_payment_refund_events_refund_id", table_name="payment_refund_events"
    )
    op.drop_index(
        "idx_payment_refund_events_org_id", table_name="payment_refund_events"
    )
    op.drop_table("payment_refund_events")

    op.drop_index(
        "idx_payment_approval_requests_org_id",
        table_name="payment_approval_requests",
    )
    op.drop_table("payment_approval_requests")

    op.drop_index("uq_payment_refunds_org_idempotency", table_name="payment_refunds")
    op.drop_index("uq_payment_refunds_provider_refund_id", table_name="payment_refunds")
    op.drop_index("idx_payment_refunds_order_id", table_name="payment_refunds")
    op.drop_index("idx_payment_refunds_txn_id", table_name="payment_refunds")
    op.drop_index("idx_payment_refunds_org_id", table_name="payment_refunds")
    op.drop_table("payment_refunds")

    op.drop_table("payment_approval_policies")
