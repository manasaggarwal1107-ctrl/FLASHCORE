from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    ForeignKey,
    Identity,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    TIMESTAMP,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class SimulationRun(Base):
    __tablename__ = "simulation_runs"

    __table_args__ = (
        CheckConstraint(
            "status IN ('created', 'running', 'completed', 'failed')",
            name="chk_simulation_status",
        ),
        Index("idx_simulation_runs_org_id", "organisation_id"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        Identity(always=True),
        primary_key=True,
    )
    organisation_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("organisations.id"),
        nullable=False,
    )
    run_name: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    configuration: Mapped[dict | None] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default=text("'created'"),
    )
    started_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("NOW()"),
    )


class SimulationProduct(Base):
    __tablename__ = "simulation_products"

    __table_args__ = (
        UniqueConstraint(
            "organisation_id",
            "sku",
            name="uq_simulation_products_org_sku",
        ),
        Index("idx_simulation_products_org_id", "organisation_id"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        Identity(always=True),
        primary_key=True,
    )
    organisation_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("organisations.id"),
        nullable=False,
    )
    sku: Mapped[str] = mapped_column(String(80), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("NOW()"),
    )


class SimulationInventory(Base):
    __tablename__ = "simulation_inventory"

    __table_args__ = (
        UniqueConstraint(
            "organisation_id",
            "store_id",
            "product_id",
            name="uq_simulation_store_product",
        ),
        CheckConstraint(
            "quantity >= 0 AND reserved_quantity >= 0",
            name="chk_simulation_quantity",
        ),
        CheckConstraint(
            "reserved_quantity <= quantity",
            name="chk_simulation_reserved",
        ),
        Index("idx_simulation_inventory_org_id", "organisation_id"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        Identity(always=True),
        primary_key=True,
    )
    organisation_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("organisations.id"),
        nullable=False,
    )
    store_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("stores.store_id"),
        nullable=False,
    )
    product_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("simulation_products.id"),
        nullable=False,
    )
    quantity: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("0"),
    )
    reserved_quantity: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("0"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("NOW()"),
    )


class FlashSale(Base):
    __tablename__ = "flash_sales"

    __table_args__ = (
        CheckConstraint(
            "ends_at > starts_at",
            name="chk_flash_sale_dates",
        ),
        CheckConstraint(
            "status IN ('draft', 'scheduled', 'active', 'completed', 'cancelled')",
            name="chk_flash_sale_status",
        ),
        Index("idx_flash_sales_org_id", "organisation_id"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        Identity(always=True),
        primary_key=True,
    )
    organisation_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("organisations.id"),
        nullable=False,
    )
    simulation_run_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("simulation_runs.id"),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    starts_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
    )
    ends_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default=text("'draft'"),
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("NOW()"),
    )


class FlashSaleProduct(Base):
    __tablename__ = "flash_sale_products"

    __table_args__ = (
        UniqueConstraint(
            "flash_sale_id",
            "inventory_id",
            name="uq_flash_sale_inventory",
        ),
        CheckConstraint("sale_price >= 0", name="chk_sale_price"),
        CheckConstraint(
            "stock_limit > 0 AND sold_quantity >= 0 AND sold_quantity <= stock_limit",
            name="chk_sale_stock",
        ),
        Index("idx_flash_sale_products_org_id", "organisation_id"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        Identity(always=True),
        primary_key=True,
    )
    organisation_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("organisations.id"),
        nullable=False,
    )
    flash_sale_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("flash_sales.id"),
        nullable=False,
    )
    inventory_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("simulation_inventory.id"),
        nullable=False,
    )
    sale_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    stock_limit: Mapped[int] = mapped_column(Integer, nullable=False)
    sold_quantity: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("0"),
    )


class PurchaseAttempt(Base):
    __tablename__ = "purchase_attempts"

    __table_args__ = (
        UniqueConstraint(
            "organisation_id",
            "idempotency_key",
            name="uq_purchase_attempts_org_idempotency_key",
        ),
        CheckConstraint("quantity > 0", name="chk_purchase_quantity"),
        CheckConstraint(
            "status IN ('pending', 'success', 'rejected', 'failed')",
            name="chk_purchase_status",
        ),
        Index(
            "uq_successful_customer_purchase",
            "organisation_id",
            "customer_ref",
            "flash_sale_product_id",
            unique=True,
            postgresql_where=text("status = 'success'"),
        ),
        Index("idx_purchase_attempts_run", "simulation_run_id"),
        Index("idx_purchase_attempts_status", "status"),
        Index("idx_purchase_attempts_org_id", "organisation_id"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        Identity(always=True),
        primary_key=True,
    )
    organisation_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("organisations.id"),
        nullable=False,
    )
    simulation_run_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("simulation_runs.id"),
        nullable=False,
    )
    flash_sale_product_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("flash_sale_products.id"),
        nullable=False,
    )
    customer_ref: Mapped[str] = mapped_column(String(100), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    quantity: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("1"),
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default=text("'pending'"),
    )
    failure_reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("NOW()"),
    )


class TransactionLog(Base):
    __tablename__ = "transactions_log"

    __table_args__ = (
        Index("idx_transactions_log_org_id", "organisation_id"),
        Index("idx_transactions_log_run_id", "simulation_run_id"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        Identity(always=True),
        primary_key=True,
    )
    organisation_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("organisations.id"),
        nullable=False,
    )
    simulation_run_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("simulation_runs.id"),
        nullable=False,
    )
    purchase_attempt_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("purchase_attempts.id"),
    )
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    outcome: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("NOW()"),
    )
