"""Active 14-table baseline schema (rossmann_schema.sql + 0001_auth_tables.sql).

Revision ID: 0001_active_baseline
Revises:
Create Date: 2026-11-26

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0001_active_baseline"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "dataset_imports",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("source_name", sa.String(length=150), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("source_file", sa.String(length=255), nullable=False),
        sa.Column("source_split", sa.String(length=30), nullable=False),
        sa.Column("checksum_sha256", sa.String(length=64), nullable=True),
        sa.Column(
            "imported_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.Column(
            "total_rows",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "successful_rows",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "rejected_rows",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(length=20),
            server_default=sa.text("'pending'"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'running', 'completed', 'failed')",
            name="chk_import_status",
        ),
        sa.CheckConstraint(
            "total_rows >= 0 AND successful_rows >= 0 AND rejected_rows >= 0",
            name="chk_import_counts",
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "dataset_import_errors",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("import_id", sa.BigInteger(), nullable=False),
        sa.Column("source_row_number", sa.Integer(), nullable=True),
        sa.Column("raw_record", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["import_id"], ["dataset_imports.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "stores",
        sa.Column("store_id", sa.Integer(), autoincrement=False, nullable=False),
        sa.Column("store_type", sa.String(length=1), nullable=True),
        sa.Column("assortment", sa.String(length=1), nullable=True),
        sa.Column("competition_distance", sa.Integer(), nullable=True),
        sa.Column("competition_open_since_month", sa.Integer(), nullable=True),
        sa.Column("competition_open_since_year", sa.Integer(), nullable=True),
        sa.Column("promo2", sa.Boolean(), nullable=True),
        sa.Column("promo2_since_week", sa.Integer(), nullable=True),
        sa.Column("promo2_since_year", sa.Integer(), nullable=True),
        sa.Column("promo_interval", sa.String(length=100), nullable=True),
        sa.Column("metadata_import_id", sa.BigInteger(), nullable=True),
        sa.CheckConstraint(
            "store_type IS NULL OR store_type IN ('a', 'b', 'c', 'd')",
            name="chk_store_type",
        ),
        sa.CheckConstraint(
            "assortment IS NULL OR assortment IN ('a', 'b', 'c')",
            name="chk_assortment",
        ),
        sa.CheckConstraint(
            "competition_distance IS NULL OR competition_distance >= 0",
            name="chk_competition_distance",
        ),
        sa.ForeignKeyConstraint(["metadata_import_id"], ["dataset_imports.id"]),
        sa.PrimaryKeyConstraint("store_id"),
    )

    op.create_table(
        "daily_store_sales",
        sa.Column("store_id", sa.Integer(), nullable=False),
        sa.Column("sales_date", sa.Date(), nullable=False),
        sa.Column("day_of_week", sa.SmallInteger(), nullable=False),
        sa.Column("sales", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("customers", sa.Integer(), nullable=False),
        sa.Column("is_open", sa.Boolean(), nullable=False),
        sa.Column("promo", sa.Boolean(), nullable=False),
        sa.Column(
            "state_holiday",
            sa.String(length=1),
            server_default=sa.text("'0'"),
            nullable=False,
        ),
        sa.Column("school_holiday", sa.Boolean(), nullable=False),
        sa.Column("import_id", sa.BigInteger(), nullable=False),
        sa.Column("source_row_number", sa.Integer(), nullable=True),
        sa.CheckConstraint("day_of_week BETWEEN 1 AND 7", name="chk_day_of_week"),
        sa.CheckConstraint("sales >= 0", name="chk_sales"),
        sa.CheckConstraint("customers >= 0", name="chk_customers"),
        sa.CheckConstraint(
            "state_holiday IN ('0', 'a', 'b', 'c')", name="chk_state_holiday"
        ),
        sa.ForeignKeyConstraint(["import_id"], ["dataset_imports.id"]),
        sa.ForeignKeyConstraint(["store_id"], ["stores.store_id"]),
        sa.PrimaryKeyConstraint("store_id", "sales_date"),
    )
    op.create_index("idx_daily_sales_date", "daily_store_sales", ["sales_date"])
    op.create_index(
        "idx_daily_sales_store_date", "daily_store_sales", ["store_id", "sales_date"]
    )
    op.create_index("idx_daily_sales_promo", "daily_store_sales", ["promo"])

    op.create_table(
        "simulation_runs",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("run_name", sa.String(length=150), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "configuration", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
        sa.Column(
            "status",
            sa.String(length=20),
            server_default=sa.text("'created'"),
            nullable=False,
        ),
        sa.Column("started_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("completed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('created', 'running', 'completed', 'failed')",
            name="chk_simulation_status",
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "simulation_products",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("sku", sa.String(length=80), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("sku", name="simulation_products_sku_key"),
    )

    op.create_table(
        "simulation_inventory",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("store_id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.BigInteger(), nullable=False),
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
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "quantity >= 0 AND reserved_quantity >= 0",
            name="chk_simulation_quantity",
        ),
        sa.CheckConstraint(
            "reserved_quantity <= quantity", name="chk_simulation_reserved"
        ),
        sa.ForeignKeyConstraint(["product_id"], ["simulation_products.id"]),
        sa.ForeignKeyConstraint(["store_id"], ["stores.store_id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "store_id", "product_id", name="uq_simulation_store_product"
        ),
    )

    op.create_table(
        "flash_sales",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("simulation_run_id", sa.BigInteger(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("starts_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("ends_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column(
            "status",
            sa.String(length=20),
            server_default=sa.text("'draft'"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.CheckConstraint("ends_at > starts_at", name="chk_flash_sale_dates"),
        sa.CheckConstraint(
            "status IN ('draft', 'scheduled', 'active', 'completed', 'cancelled')",
            name="chk_flash_sale_status",
        ),
        sa.ForeignKeyConstraint(["simulation_run_id"], ["simulation_runs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "flash_sale_products",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("flash_sale_id", sa.BigInteger(), nullable=False),
        sa.Column("inventory_id", sa.BigInteger(), nullable=False),
        sa.Column("sale_price", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("stock_limit", sa.Integer(), nullable=False),
        sa.Column(
            "sold_quantity",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.CheckConstraint("sale_price >= 0", name="chk_sale_price"),
        sa.CheckConstraint(
            "stock_limit > 0 AND sold_quantity >= 0 AND sold_quantity <= stock_limit",
            name="chk_sale_stock",
        ),
        sa.ForeignKeyConstraint(["flash_sale_id"], ["flash_sales.id"]),
        sa.ForeignKeyConstraint(["inventory_id"], ["simulation_inventory.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "flash_sale_id", "inventory_id", name="uq_flash_sale_inventory"
        ),
    )

    op.create_table(
        "purchase_attempts",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("simulation_run_id", sa.BigInteger(), nullable=False),
        sa.Column("flash_sale_product_id", sa.BigInteger(), nullable=False),
        sa.Column("customer_ref", sa.String(length=100), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column(
            "quantity", sa.Integer(), server_default=sa.text("1"), nullable=False
        ),
        sa.Column(
            "status",
            sa.String(length=20),
            server_default=sa.text("'pending'"),
            nullable=False,
        ),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.CheckConstraint("quantity > 0", name="chk_purchase_quantity"),
        sa.CheckConstraint(
            "status IN ('pending', 'success', 'rejected', 'failed')",
            name="chk_purchase_status",
        ),
        sa.ForeignKeyConstraint(
            ["flash_sale_product_id"], ["flash_sale_products.id"]
        ),
        sa.ForeignKeyConstraint(["simulation_run_id"], ["simulation_runs.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "idempotency_key", name="purchase_attempts_idempotency_key_key"
        ),
    )
    op.create_index(
        "uq_successful_customer_purchase",
        "purchase_attempts",
        ["customer_ref", "flash_sale_product_id"],
        unique=True,
        postgresql_where=sa.text("status = 'success'"),
    )
    op.create_index(
        "idx_purchase_attempts_run", "purchase_attempts", ["simulation_run_id"]
    )
    op.create_index("idx_purchase_attempts_status", "purchase_attempts", ["status"])

    op.create_table(
        "transactions_log",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("simulation_run_id", sa.BigInteger(), nullable=False),
        sa.Column("purchase_attempt_id", sa.BigInteger(), nullable=True),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("outcome", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["purchase_attempt_id"], ["purchase_attempts.id"]),
        sa.ForeignKeyConstraint(["simulation_run_id"], ["simulation_runs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("actor_type", sa.String(length=50), nullable=True),
        sa.Column("actor_ref", sa.String(length=100), nullable=True),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("entity_name", sa.String(length=100), nullable=False),
        sa.Column("entity_id", sa.String(length=100), nullable=True),
        sa.Column("details", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_audit_entity", "audit_logs", ["entity_name", "entity_id"])

    op.create_table(
        "users",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column(
            "role",
            sa.String(length=20),
            server_default=sa.text("'analyst'"),
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
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "role IN ('admin', 'analyst', 'operator')", name="chk_users_role"
        ),
        sa.CheckConstraint(
            "status IN ('active', 'disabled')", name="chk_users_status"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "uq_users_email_lower", "users", [sa.text("LOWER(email)")], unique=True
    )

    op.create_table(
        "auth_sessions",
        sa.Column("jti", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("jti"),
    )
    op.create_index("idx_auth_sessions_user_id", "auth_sessions", ["user_id"])
    op.create_index("idx_auth_sessions_expires_at", "auth_sessions", ["expires_at"])


def downgrade() -> None:
    op.drop_index("idx_auth_sessions_expires_at", table_name="auth_sessions")
    op.drop_index("idx_auth_sessions_user_id", table_name="auth_sessions")
    op.drop_table("auth_sessions")

    op.drop_index("uq_users_email_lower", table_name="users")
    op.drop_table("users")

    op.drop_index("idx_audit_entity", table_name="audit_logs")
    op.drop_table("audit_logs")

    op.drop_table("transactions_log")

    op.drop_index("idx_purchase_attempts_status", table_name="purchase_attempts")
    op.drop_index("idx_purchase_attempts_run", table_name="purchase_attempts")
    op.drop_index("uq_successful_customer_purchase", table_name="purchase_attempts")
    op.drop_table("purchase_attempts")

    op.drop_table("flash_sale_products")
    op.drop_table("flash_sales")
    op.drop_table("simulation_inventory")
    op.drop_table("simulation_products")
    op.drop_table("simulation_runs")

    op.drop_index("idx_daily_sales_promo", table_name="daily_store_sales")
    op.drop_index("idx_daily_sales_store_date", table_name="daily_store_sales")
    op.drop_index("idx_daily_sales_date", table_name="daily_store_sales")
    op.drop_table("daily_store_sales")

    op.drop_table("stores")
    op.drop_table("dataset_import_errors")
    op.drop_table("dataset_imports")
