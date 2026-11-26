"""Add real tenant-scoped commerce and merchant payment tables.

Revision ID: 0003_commerce_and_payments
Revises: 0002_organisations_and_tenancy
Create Date: 2026-11-26

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0003_commerce_and_payments"
down_revision: Union[str, Sequence[str], None] = "0002_organisations_and_tenancy"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "commerce_products",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("organisation_id", sa.BigInteger(), nullable=False),
        sa.Column("sku", sa.String(length=80), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("category", sa.String(length=120), nullable=True),
        sa.Column(
            "status",
            sa.String(length=20),
            server_default=sa.text("'draft'"),
            nullable=False,
        ),
        sa.Column("price_minor", sa.BigInteger(), nullable=False),
        sa.Column(
            "currency",
            sa.String(length=3),
            server_default=sa.text("'INR'"),
            nullable=False,
        ),
        sa.Column(
            "tax_rate_bps",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
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
            "status IN ('draft', 'active', 'archived')",
            name="chk_commerce_products_status",
        ),
        sa.CheckConstraint("price_minor >= 0", name="chk_commerce_products_price"),
        sa.CheckConstraint(
            "char_length(currency) = 3", name="chk_commerce_products_currency"
        ),
        sa.CheckConstraint(
            "tax_rate_bps >= 0 AND tax_rate_bps <= 10000",
            name="chk_commerce_products_tax_rate",
        ),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organisation_id", "sku", name="uq_commerce_products_org_sku"
        ),
    )
    op.create_index(
        "idx_commerce_products_org_id", "commerce_products", ["organisation_id"]
    )
    op.create_index(
        "idx_commerce_products_org_status",
        "commerce_products",
        ["organisation_id", "status"],
    )

    op.create_table(
        "inventory_locations",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("organisation_id", sa.BigInteger(), nullable=False),
        sa.Column("code", sa.String(length=60), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column(
            "location_type",
            sa.String(length=30),
            server_default=sa.text("'warehouse'"),
            nullable=False,
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.text("TRUE"),
            nullable=False,
        ),
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
            "location_type IN ('warehouse', 'store', 'fulfilment_centre')",
            name="chk_inventory_locations_type",
        ),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organisation_id", "code", name="uq_inventory_locations_org_code"
        ),
    )
    op.create_index(
        "idx_inventory_locations_org_id", "inventory_locations", ["organisation_id"]
    )

    op.create_table(
        "inventory_balances",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("organisation_id", sa.BigInteger(), nullable=False),
        sa.Column("product_id", sa.BigInteger(), nullable=False),
        sa.Column("location_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "quantity", sa.Integer(), server_default=sa.text("0"), nullable=False
        ),
        sa.Column(
            "reserved_quantity",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "low_stock_threshold",
            sa.Integer(),
            server_default=sa.text("5"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.CheckConstraint("quantity >= 0", name="chk_inventory_balances_quantity"),
        sa.CheckConstraint(
            "reserved_quantity >= 0", name="chk_inventory_balances_reserved"
        ),
        sa.CheckConstraint(
            "reserved_quantity <= quantity",
            name="chk_inventory_balances_invariant",
        ),
        sa.CheckConstraint(
            "low_stock_threshold >= 0", name="chk_inventory_balances_threshold"
        ),
        sa.ForeignKeyConstraint(["location_id"], ["inventory_locations.id"]),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"]),
        sa.ForeignKeyConstraint(["product_id"], ["commerce_products.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organisation_id",
            "product_id",
            "location_id",
            name="uq_inventory_balances_org_prod_loc",
        ),
    )
    op.create_index(
        "idx_inventory_balances_org_id", "inventory_balances", ["organisation_id"]
    )
    op.create_index(
        "idx_inventory_balances_product_id", "inventory_balances", ["product_id"]
    )
    op.create_index(
        "idx_inventory_balances_location_id", "inventory_balances", ["location_id"]
    )

    op.create_table(
        "inventory_movements",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("organisation_id", sa.BigInteger(), nullable=False),
        sa.Column("balance_id", sa.BigInteger(), nullable=False),
        sa.Column("product_id", sa.BigInteger(), nullable=False),
        sa.Column("location_id", sa.BigInteger(), nullable=False),
        sa.Column("movement_type", sa.String(length=30), nullable=False),
        sa.Column("quantity_delta", sa.Integer(), nullable=False),
        sa.Column(
            "reserved_delta",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column("balance_after", sa.Integer(), nullable=False),
        sa.Column("reserved_after", sa.Integer(), nullable=False),
        sa.Column("reference_type", sa.String(length=60), nullable=True),
        sa.Column("reference_id", sa.String(length=100), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("actor_ref", sa.String(length=150), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "movement_type IN ('adjustment', 'reservation', 'release', 'expiry', 'fulfilment', 'sale')",
            name="chk_inventory_movements_type",
        ),
        sa.CheckConstraint(
            "balance_after >= 0 AND reserved_after >= 0",
            name="chk_inventory_movements_balances",
        ),
        sa.ForeignKeyConstraint(["balance_id"], ["inventory_balances.id"]),
        sa.ForeignKeyConstraint(["location_id"], ["inventory_locations.id"]),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"]),
        sa.ForeignKeyConstraint(["product_id"], ["commerce_products.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_inventory_movements_org_id", "inventory_movements", ["organisation_id"]
    )
    op.create_index(
        "idx_inventory_movements_balance_id", "inventory_movements", ["balance_id"]
    )
    op.create_index(
        "idx_inventory_movements_created_at", "inventory_movements", ["created_at"]
    )

    op.create_table(
        "customers",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("organisation_id", sa.BigInteger(), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=True),
        sa.Column("phone", sa.String(length=30), nullable=True),
        sa.Column(
            "billing_address", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
        sa.Column(
            "shipping_address", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
        sa.Column(
            "status",
            sa.String(length=20),
            server_default=sa.text("'active'"),
            nullable=False,
        ),
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
            "status IN ('active', 'inactive')", name="chk_customers_status"
        ),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_customers_org_id", "customers", ["organisation_id"])
    op.create_index(
        "uq_customers_org_email_lower",
        "customers",
        ["organisation_id", sa.text("LOWER(email)")],
        unique=True,
        postgresql_where=sa.text("email IS NOT NULL"),
    )

    op.create_table(
        "orders",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("organisation_id", sa.BigInteger(), nullable=False),
        sa.Column("customer_id", sa.BigInteger(), nullable=True),
        sa.Column("order_number", sa.String(length=60), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=True),
        sa.Column(
            "currency",
            sa.String(length=3),
            server_default=sa.text("'INR'"),
            nullable=False,
        ),
        sa.Column("subtotal_minor", sa.BigInteger(), nullable=False),
        sa.Column(
            "discount_minor",
            sa.BigInteger(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "tax_minor",
            sa.BigInteger(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column("total_minor", sa.BigInteger(), nullable=False),
        sa.Column(
            "order_status",
            sa.String(length=30),
            server_default=sa.text("'DRAFT'"),
            nullable=False,
        ),
        sa.Column(
            "payment_status",
            sa.String(length=30),
            server_default=sa.text("'UNPAID'"),
            nullable=False,
        ),
        sa.Column(
            "customer_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
        sa.Column(
            "reservation_expires_at", sa.TIMESTAMP(timezone=True), nullable=True
        ),
        sa.Column(
            "placed_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
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
        sa.CheckConstraint("subtotal_minor >= 0", name="chk_orders_subtotal"),
        sa.CheckConstraint("discount_minor >= 0", name="chk_orders_discount"),
        sa.CheckConstraint("tax_minor >= 0", name="chk_orders_tax"),
        sa.CheckConstraint("total_minor >= 0", name="chk_orders_total"),
        sa.CheckConstraint(
            "order_status IN ('DRAFT', 'PENDING_PAYMENT', 'PAID', 'PROCESSING', 'FULFILLED', 'CANCELLED', 'EXPIRED')",
            name="chk_orders_order_status",
        ),
        sa.CheckConstraint(
            "payment_status IN ('UNPAID', 'CREATED', 'PENDING', 'AUTHORIZED', 'CAPTURED', 'FAILED', 'CANCELLED')",
            name="chk_orders_payment_status",
        ),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"]),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organisation_id", "order_number", name="uq_orders_org_number"
        ),
    )
    op.create_index("idx_orders_org_id", "orders", ["organisation_id"])
    op.create_index("idx_orders_customer_id", "orders", ["customer_id"])
    op.create_index(
        "idx_orders_org_status", "orders", ["organisation_id", "order_status"]
    )
    op.create_index("idx_orders_placed_at", "orders", ["placed_at"])
    op.create_index(
        "uq_orders_org_idempotency",
        "orders",
        ["organisation_id", "idempotency_key"],
        unique=True,
        postgresql_where=sa.text("idempotency_key IS NOT NULL"),
    )

    op.create_table(
        "order_items",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("organisation_id", sa.BigInteger(), nullable=False),
        sa.Column("order_id", sa.BigInteger(), nullable=False),
        sa.Column("product_id", sa.BigInteger(), nullable=False),
        sa.Column("location_id", sa.BigInteger(), nullable=False),
        sa.Column("sku_snapshot", sa.String(length=80), nullable=False),
        sa.Column("name_snapshot", sa.String(length=200), nullable=False),
        sa.Column("unit_price_minor", sa.BigInteger(), nullable=False),
        sa.Column(
            "tax_rate_bps",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column(
            "tax_minor",
            sa.BigInteger(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column("line_total_minor", sa.BigInteger(), nullable=False),
        sa.CheckConstraint("quantity > 0", name="chk_order_items_quantity"),
        sa.CheckConstraint("unit_price_minor >= 0", name="chk_order_items_unit_price"),
        sa.CheckConstraint("tax_minor >= 0", name="chk_order_items_tax"),
        sa.CheckConstraint("line_total_minor >= 0", name="chk_order_items_total"),
        sa.ForeignKeyConstraint(["location_id"], ["inventory_locations.id"]),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"]),
        sa.ForeignKeyConstraint(["product_id"], ["commerce_products.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_order_items_org_id", "order_items", ["organisation_id"])
    op.create_index("idx_order_items_order_id", "order_items", ["order_id"])

    op.create_table(
        "inventory_reservations",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("organisation_id", sa.BigInteger(), nullable=False),
        sa.Column("order_id", sa.BigInteger(), nullable=False),
        sa.Column("order_item_id", sa.BigInteger(), nullable=False),
        sa.Column("balance_id", sa.BigInteger(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.String(length=20),
            server_default=sa.text("'PENDING'"),
            nullable=False,
        ),
        sa.Column("expires_at", sa.TIMESTAMP(timezone=True), nullable=False),
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
        sa.CheckConstraint("quantity > 0", name="chk_inventory_reservations_quantity"),
        sa.CheckConstraint(
            "status IN ('PENDING', 'CONFIRMED', 'RELEASED', 'EXPIRED')",
            name="chk_inventory_reservations_status",
        ),
        sa.ForeignKeyConstraint(["balance_id"], ["inventory_balances.id"]),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["order_item_id"], ["order_items.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_inventory_reservations_org_status_exp",
        "inventory_reservations",
        ["organisation_id", "status", "expires_at"],
    )
    op.create_index(
        "idx_inventory_reservations_order_id", "inventory_reservations", ["order_id"]
    )

    op.create_table(
        "order_events",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("organisation_id", sa.BigInteger(), nullable=False),
        sa.Column("order_id", sa.BigInteger(), nullable=False),
        sa.Column("from_status", sa.String(length=30), nullable=True),
        sa.Column("to_status", sa.String(length=30), nullable=False),
        sa.Column("event_type", sa.String(length=60), nullable=False),
        sa.Column("actor_ref", sa.String(length=150), nullable=True),
        sa.Column("details", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_order_events_org_id", "order_events", ["organisation_id"])
    op.create_index("idx_order_events_order_id", "order_events", ["order_id"])

    op.create_table(
        "payment_provider_accounts",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("organisation_id", sa.BigInteger(), nullable=False),
        sa.Column("provider", sa.String(length=30), nullable=False),
        sa.Column(
            "mode",
            sa.String(length=10),
            server_default=sa.text("'test'"),
            nullable=False,
        ),
        sa.Column("key_id", sa.String(length=120), nullable=False),
        sa.Column("encrypted_key_secret", sa.Text(), nullable=False),
        sa.Column("encrypted_webhook_secret", sa.Text(), nullable=False),
        sa.Column(
            "key_version",
            sa.String(length=40),
            server_default=sa.text("'v1'"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(length=20),
            server_default=sa.text("'active'"),
            nullable=False,
        ),
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
            "provider IN ('razorpay')", name="chk_payment_accounts_provider"
        ),
        sa.CheckConstraint("mode IN ('test', 'live')", name="chk_payment_accounts_mode"),
        sa.CheckConstraint(
            "status IN ('active', 'disabled')", name="chk_payment_accounts_status"
        ),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key_id", name="uq_payment_accounts_key_id"),
        sa.UniqueConstraint(
            "organisation_id",
            "provider",
            "mode",
            name="uq_payment_accounts_org_provider_mode",
        ),
    )
    op.create_index(
        "idx_payment_accounts_org_id", "payment_provider_accounts", ["organisation_id"]
    )

    op.create_table(
        "payment_orders",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("organisation_id", sa.BigInteger(), nullable=False),
        sa.Column("order_id", sa.BigInteger(), nullable=False),
        sa.Column("provider_account_id", sa.BigInteger(), nullable=False),
        sa.Column("provider", sa.String(length=30), nullable=False),
        sa.Column("provider_order_id", sa.String(length=120), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=True),
        sa.Column("amount_minor", sa.BigInteger(), nullable=False),
        sa.Column(
            "currency",
            sa.String(length=3),
            server_default=sa.text("'INR'"),
            nullable=False,
        ),
        sa.Column("receipt", sa.String(length=80), nullable=False),
        sa.Column(
            "status",
            sa.String(length=20),
            server_default=sa.text("'CREATED'"),
            nullable=False,
        ),
        sa.Column(
            "provider_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
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
        sa.CheckConstraint("amount_minor > 0", name="chk_payment_orders_amount"),
        sa.CheckConstraint(
            "status IN ('CREATED', 'PENDING', 'AUTHORIZED', 'CAPTURED', 'FAILED', 'CANCELLED')",
            name="chk_payment_orders_status",
        ),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"]),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"]),
        sa.ForeignKeyConstraint(
            ["provider_account_id"], ["payment_provider_accounts.id"]
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "provider",
            "provider_order_id",
            name="uq_payment_orders_provider_order_id",
        ),
    )
    op.create_index("idx_payment_orders_org_id", "payment_orders", ["organisation_id"])
    op.create_index("idx_payment_orders_order_id", "payment_orders", ["order_id"])
    op.create_index(
        "uq_payment_orders_org_idempotency",
        "payment_orders",
        ["organisation_id", "idempotency_key"],
        unique=True,
        postgresql_where=sa.text("idempotency_key IS NOT NULL"),
    )

    op.create_table(
        "payment_attempts",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("organisation_id", sa.BigInteger(), nullable=False),
        sa.Column("payment_order_id", sa.BigInteger(), nullable=False),
        sa.Column("order_id", sa.BigInteger(), nullable=False),
        sa.Column("provider", sa.String(length=30), nullable=False),
        sa.Column("provider_payment_id", sa.String(length=120), nullable=True),
        sa.Column(
            "status",
            sa.String(length=20),
            server_default=sa.text("'CREATED'"),
            nullable=False,
        ),
        sa.Column("failure_code", sa.String(length=80), nullable=True),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column(
            "signature_verified",
            sa.Boolean(),
            server_default=sa.text("FALSE"),
            nullable=False,
        ),
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
            "status IN ('CREATED', 'PENDING', 'AUTHORIZED', 'CAPTURED', 'FAILED', 'CANCELLED')",
            name="chk_payment_attempts_status",
        ),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"]),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"]),
        sa.ForeignKeyConstraint(["payment_order_id"], ["payment_orders.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_payment_attempts_org_id", "payment_attempts", ["organisation_id"]
    )
    op.create_index(
        "idx_payment_attempts_payment_order_id",
        "payment_attempts",
        ["payment_order_id"],
    )
    op.create_index(
        "uq_payment_attempts_provider_payment_id",
        "payment_attempts",
        ["provider", "provider_payment_id"],
        unique=True,
        postgresql_where=sa.text("provider_payment_id IS NOT NULL"),
    )

    op.create_table(
        "payment_transactions",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("organisation_id", sa.BigInteger(), nullable=False),
        sa.Column("order_id", sa.BigInteger(), nullable=False),
        sa.Column("payment_order_id", sa.BigInteger(), nullable=False),
        sa.Column("payment_attempt_id", sa.BigInteger(), nullable=True),
        sa.Column("provider", sa.String(length=30), nullable=False),
        sa.Column("provider_payment_id", sa.String(length=120), nullable=False),
        sa.Column("event_type", sa.String(length=40), nullable=False),
        sa.Column("amount_minor", sa.BigInteger(), nullable=False),
        sa.Column(
            "currency",
            sa.String(length=3),
            server_default=sa.text("'INR'"),
            nullable=False,
        ),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("method", sa.String(length=40), nullable=True),
        sa.Column("source", sa.String(length=30), nullable=False),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "event_type IN ('AUTHORIZED', 'CAPTURED', 'FAILED', 'CANCELLED')",
            name="chk_payment_transactions_event_type",
        ),
        sa.CheckConstraint("amount_minor >= 0", name="chk_payment_transactions_amount"),
        sa.CheckConstraint(
            "status IN ('CREATED', 'PENDING', 'AUTHORIZED', 'CAPTURED', 'FAILED', 'CANCELLED')",
            name="chk_payment_transactions_status",
        ),
        sa.CheckConstraint(
            "source IN ('checkout_verify', 'webhook')",
            name="chk_payment_transactions_source",
        ),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"]),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"]),
        sa.ForeignKeyConstraint(["payment_attempt_id"], ["payment_attempts.id"]),
        sa.ForeignKeyConstraint(["payment_order_id"], ["payment_orders.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "provider",
            "provider_payment_id",
            "event_type",
            name="uq_payment_transactions_provider_event",
        ),
    )
    op.create_index(
        "idx_payment_transactions_org_id", "payment_transactions", ["organisation_id"]
    )
    op.create_index(
        "idx_payment_transactions_order_id", "payment_transactions", ["order_id"]
    )
    op.create_index(
        "idx_payment_transactions_created_at", "payment_transactions", ["created_at"]
    )

    op.create_table(
        "payment_webhook_events",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("organisation_id", sa.BigInteger(), nullable=True),
        sa.Column("provider_account_id", sa.BigInteger(), nullable=True),
        sa.Column("provider", sa.String(length=30), nullable=False),
        sa.Column("provider_event_id", sa.String(length=120), nullable=False),
        sa.Column("event_type", sa.String(length=80), nullable=False),
        sa.Column("provider_order_id", sa.String(length=120), nullable=True),
        sa.Column("provider_payment_id", sa.String(length=120), nullable=True),
        sa.Column(
            "signature_valid",
            sa.Boolean(),
            server_default=sa.text("FALSE"),
            nullable=False,
        ),
        sa.Column(
            "processing_status",
            sa.String(length=30),
            server_default=sa.text("'received'"),
            nullable=False,
        ),
        sa.Column("payload_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "sanitized_summary", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "received_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.Column("processed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.CheckConstraint(
            "processing_status IN ('received', 'processed', 'ignored_duplicate', 'ignored_out_of_order', 'rejected_signature', 'failed')",
            name="chk_payment_webhook_events_status",
        ),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"]),
        sa.ForeignKeyConstraint(
            ["provider_account_id"], ["payment_provider_accounts.id"]
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "provider",
            "provider_event_id",
            name="uq_payment_webhook_events_provider_event_id",
        ),
    )
    op.create_index(
        "idx_payment_webhook_events_org_id",
        "payment_webhook_events",
        ["organisation_id"],
    )


def downgrade() -> None:
    op.drop_index("idx_payment_webhook_events_org_id", table_name="payment_webhook_events")
    op.drop_table("payment_webhook_events")

    op.drop_index("idx_payment_transactions_created_at", table_name="payment_transactions")
    op.drop_index("idx_payment_transactions_order_id", table_name="payment_transactions")
    op.drop_index("idx_payment_transactions_org_id", table_name="payment_transactions")
    op.drop_table("payment_transactions")

    op.drop_index(
        "uq_payment_attempts_provider_payment_id", table_name="payment_attempts"
    )
    op.drop_index(
        "idx_payment_attempts_payment_order_id", table_name="payment_attempts"
    )
    op.drop_index("idx_payment_attempts_org_id", table_name="payment_attempts")
    op.drop_table("payment_attempts")

    op.drop_index("uq_payment_orders_org_idempotency", table_name="payment_orders")
    op.drop_index("idx_payment_orders_order_id", table_name="payment_orders")
    op.drop_index("idx_payment_orders_org_id", table_name="payment_orders")
    op.drop_table("payment_orders")

    op.drop_index("idx_payment_accounts_org_id", table_name="payment_provider_accounts")
    op.drop_table("payment_provider_accounts")

    op.drop_index("idx_order_events_order_id", table_name="order_events")
    op.drop_index("idx_order_events_org_id", table_name="order_events")
    op.drop_table("order_events")

    op.drop_index(
        "idx_inventory_reservations_order_id", table_name="inventory_reservations"
    )
    op.drop_index(
        "idx_inventory_reservations_org_status_exp",
        table_name="inventory_reservations",
    )
    op.drop_table("inventory_reservations")

    op.drop_index("idx_order_items_order_id", table_name="order_items")
    op.drop_index("idx_order_items_org_id", table_name="order_items")
    op.drop_table("order_items")

    op.drop_index("uq_orders_org_idempotency", table_name="orders")
    op.drop_index("idx_orders_placed_at", table_name="orders")
    op.drop_index("idx_orders_org_status", table_name="orders")
    op.drop_index("idx_orders_customer_id", table_name="orders")
    op.drop_index("idx_orders_org_id", table_name="orders")
    op.drop_table("orders")

    op.drop_index("uq_customers_org_email_lower", table_name="customers")
    op.drop_index("idx_customers_org_id", table_name="customers")
    op.drop_table("customers")

    op.drop_index("idx_inventory_movements_created_at", table_name="inventory_movements")
    op.drop_index("idx_inventory_movements_balance_id", table_name="inventory_movements")
    op.drop_index("idx_inventory_movements_org_id", table_name="inventory_movements")
    op.drop_table("inventory_movements")

    op.drop_index("idx_inventory_balances_location_id", table_name="inventory_balances")
    op.drop_index("idx_inventory_balances_product_id", table_name="inventory_balances")
    op.drop_index("idx_inventory_balances_org_id", table_name="inventory_balances")
    op.drop_table("inventory_balances")

    op.drop_index("idx_inventory_locations_org_id", table_name="inventory_locations")
    op.drop_table("inventory_locations")

    op.drop_index("idx_commerce_products_org_status", table_name="commerce_products")
    op.drop_index("idx_commerce_products_org_id", table_name="commerce_products")
    op.drop_table("commerce_products")
