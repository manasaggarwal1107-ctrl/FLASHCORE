"""Introduce organisations, memberships, and tenant scoping.

Revision ID: 0002_organisations_and_tenancy
Revises: 0001_active_baseline
Create Date: 2026-11-26

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0002_organisations_and_tenancy"
down_revision: Union[str, Sequence[str], None] = "0001_active_baseline"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

DEFAULT_ORG_NAME = "Default Workspace"
DEFAULT_ORG_SLUG = "default-workspace"

TENANT_NOT_NULL_TABLES = (
    "simulation_runs",
    "simulation_products",
    "simulation_inventory",
    "flash_sales",
    "flash_sale_products",
    "purchase_attempts",
    "transactions_log",
)

ORG_SIMULATION_AUDIT_ENTITIES = (
    "simulation_runs",
    "simulation_products",
    "simulation_inventory",
    "flash_sales",
    "flash_sale_products",
    "purchase_attempts",
    "transactions_log",
)


def _drop_unique_constraint_on_columns(table_name: str, columns: list[str]) -> None:
    """Drop any UNIQUE constraint on `table_name` matching exact `columns`."""
    conn = op.get_bind()
    rows = conn.execute(
        sa.text(
            """
            SELECT c.conname
            FROM pg_constraint c
            JOIN pg_class t ON t.oid = c.conrelid
            JOIN pg_namespace n ON n.oid = t.relnamespace
            WHERE n.nspname = 'public'
              AND t.relname = :table_name
              AND c.contype = 'u'
              AND (
                  SELECT ARRAY_AGG(a.attname::text ORDER BY u.ord)
                  FROM unnest(c.conkey) WITH ORDINALITY AS u(attnum, ord)
                  JOIN pg_attribute a ON a.attrelid = t.oid AND a.attnum = u.attnum
              ) = :columns
            """
        ),
        {"table_name": table_name, "columns": columns},
    ).scalars().all()
    for conname in rows:
        op.drop_constraint(conname, table_name, type_="unique")


def upgrade() -> None:
    op.create_table(
        "organisations",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("slug", sa.String(length=120), nullable=False),
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
            "status IN ('active', 'suspended', 'archived')",
            name="chk_organisations_status",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug", name="uq_organisations_slug"),
    )
    op.create_index("idx_organisations_status", "organisations", ["status"])

    op.create_table(
        "organisation_memberships",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("organisation_id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
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
            "role IN ('owner', 'admin', 'analyst', 'operator')",
            name="chk_org_memberships_role",
        ),
        sa.CheckConstraint(
            "status IN ('active', 'invited', 'revoked')",
            name="chk_org_memberships_status",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id"], ["organisations.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organisation_id", "user_id", name="uq_org_memberships_org_user"
        ),
    )
    op.create_index(
        "idx_org_memberships_user_id", "organisation_memberships", ["user_id"]
    )
    op.create_index(
        "idx_org_memberships_org_id", "organisation_memberships", ["organisation_id"]
    )

    conn = op.get_bind()
    conn.execute(
        sa.text(
            """
            INSERT INTO organisations (name, slug, status)
            VALUES (:name, :slug, 'active')
            ON CONFLICT (slug) DO NOTHING
            """
        ),
        {"name": DEFAULT_ORG_NAME, "slug": DEFAULT_ORG_SLUG},
    )
    default_org_id = conn.execute(
        sa.text("SELECT id FROM organisations WHERE slug = :slug"),
        {"slug": DEFAULT_ORG_SLUG},
    ).scalar_one()

    # Migrate existing users conservatively into the legacy/default organisation.
    conn.execute(
        sa.text(
            """
            INSERT INTO organisation_memberships (organisation_id, user_id, role, status)
            SELECT
                :org_id,
                id,
                CASE
                    WHEN role IN ('admin', 'analyst', 'operator') THEN role
                    ELSE 'analyst'
                END,
                CASE
                    WHEN status = 'active' THEN 'active'
                    ELSE 'revoked'
                END
            FROM users
            ON CONFLICT (organisation_id, user_id) DO NOTHING
            """
        ),
        {"org_id": default_org_id},
    )

    # Add nullable organisation_id columns first, then backfill.
    for table in TENANT_NOT_NULL_TABLES:
        op.add_column(
            table,
            sa.Column("organisation_id", sa.BigInteger(), nullable=True),
        )
        op.create_foreign_key(
            f"fk_{table}_organisation_id",
            table,
            "organisations",
            ["organisation_id"],
            ["id"],
        )
        conn.execute(
            sa.text(f"UPDATE {table} SET organisation_id = :org_id WHERE organisation_id IS NULL"),
            {"org_id": default_org_id},
        )
        op.alter_column(table, "organisation_id", nullable=False)
        op.create_index(f"idx_{table}_org_id", table, ["organisation_id"])

    op.create_index(
        "idx_transactions_log_run_id", "transactions_log", ["simulation_run_id"]
    )

    # audit_logs and dataset_imports support both platform-level (NULL) and org-owned records.
    for table in ("audit_logs", "dataset_imports"):
        op.add_column(
            table,
            sa.Column("organisation_id", sa.BigInteger(), nullable=True),
        )
        op.create_foreign_key(
            f"fk_{table}_organisation_id",
            table,
            "organisations",
            ["organisation_id"],
            ["id"],
        )
        op.create_index(f"idx_{table}_org_id", table, ["organisation_id"])

    conn.execute(
        sa.text(
            """
            UPDATE audit_logs
            SET organisation_id = :org_id
            WHERE organisation_id IS NULL
              AND entity_name = ANY(:entities)
            """
        ),
        {"org_id": default_org_id, "entities": list(ORG_SIMULATION_AUDIT_ENTITIES)},
    )

    # Replace global unique constraints with tenant-scoped constraints safely.
    op.create_unique_constraint(
        "uq_simulation_products_org_sku",
        "simulation_products",
        ["organisation_id", "sku"],
    )
    _drop_unique_constraint_on_columns("simulation_products", ["sku"])

    op.create_unique_constraint(
        "uq_simulation_org_store_product",
        "simulation_inventory",
        ["organisation_id", "store_id", "product_id"],
    )
    _drop_unique_constraint_on_columns("simulation_inventory", ["store_id", "product_id"])
    op.execute(
        "ALTER TABLE simulation_inventory RENAME CONSTRAINT uq_simulation_org_store_product TO uq_simulation_store_product"
    )

    op.create_unique_constraint(
        "uq_purchase_attempts_org_idempotency_key",
        "purchase_attempts",
        ["organisation_id", "idempotency_key"],
    )
    _drop_unique_constraint_on_columns("purchase_attempts", ["idempotency_key"])

    op.create_index(
        "uq_successful_customer_purchase_org",
        "purchase_attempts",
        ["organisation_id", "customer_ref", "flash_sale_product_id"],
        unique=True,
        postgresql_where=sa.text("status = 'success'"),
    )
    op.drop_index("uq_successful_customer_purchase", table_name="purchase_attempts")
    op.execute(
        "ALTER INDEX uq_successful_customer_purchase_org RENAME TO uq_successful_customer_purchase"
    )


def downgrade() -> None:
    op.create_index(
        "uq_successful_customer_purchase_global",
        "purchase_attempts",
        ["customer_ref", "flash_sale_product_id"],
        unique=True,
        postgresql_where=sa.text("status = 'success'"),
    )
    op.drop_index("uq_successful_customer_purchase", table_name="purchase_attempts")
    op.execute(
        "ALTER INDEX uq_successful_customer_purchase_global RENAME TO uq_successful_customer_purchase"
    )

    op.create_unique_constraint(
        "purchase_attempts_idempotency_key_key",
        "purchase_attempts",
        ["idempotency_key"],
    )
    op.drop_constraint(
        "uq_purchase_attempts_org_idempotency_key",
        "purchase_attempts",
        type_="unique",
    )

    op.create_unique_constraint(
        "uq_simulation_store_product_global",
        "simulation_inventory",
        ["store_id", "product_id"],
    )
    op.drop_constraint(
        "uq_simulation_store_product",
        "simulation_inventory",
        type_="unique",
    )
    op.execute(
        "ALTER TABLE simulation_inventory RENAME CONSTRAINT uq_simulation_store_product_global TO uq_simulation_store_product"
    )

    op.create_unique_constraint(
        "simulation_products_sku_key",
        "simulation_products",
        ["sku"],
    )
    op.drop_constraint(
        "uq_simulation_products_org_sku",
        "simulation_products",
        type_="unique",
    )

    for table in ("dataset_imports", "audit_logs"):
        op.drop_index(f"idx_{table}_org_id", table_name=table)
        op.drop_constraint(f"fk_{table}_organisation_id", table, type_="foreignkey")
        op.drop_column(table, "organisation_id")

    op.drop_index("idx_transactions_log_run_id", table_name="transactions_log")

    for table in reversed(TENANT_NOT_NULL_TABLES):
        op.drop_index(f"idx_{table}_org_id", table_name=table)
        op.drop_constraint(f"fk_{table}_organisation_id", table, type_="foreignkey")
        op.drop_column(table, "organisation_id")

    op.drop_index("idx_org_memberships_org_id", table_name="organisation_memberships")
    op.drop_index("idx_org_memberships_user_id", table_name="organisation_memberships")
    op.drop_table("organisation_memberships")

    op.drop_index("idx_organisations_status", table_name="organisations")
    op.drop_table("organisations")
