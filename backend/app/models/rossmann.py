from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    Identity,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    TIMESTAMP,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class DatasetImport(Base):
    __tablename__ = "dataset_imports"

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'running', 'completed', 'failed')",
            name="chk_import_status",
        ),
        CheckConstraint(
            "total_rows >= 0 AND successful_rows >= 0 AND rejected_rows >= 0",
            name="chk_import_counts",
        ),
        Index("idx_dataset_imports_org_id", "organisation_id"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        Identity(always=True),
        primary_key=True,
    )
    organisation_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("organisations.id"),
        nullable=True,
    )
    source_name: Mapped[str] = mapped_column(String(150), nullable=False)
    source_url: Mapped[str | None] = mapped_column(Text)
    source_file: Mapped[str] = mapped_column(String(255), nullable=False)
    source_split: Mapped[str] = mapped_column(String(30), nullable=False)
    checksum_sha256: Mapped[str | None] = mapped_column(String(64))
    imported_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("NOW()"),
    )
    total_rows: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    successful_rows: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    rejected_rows: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'pending'")
    )


class Store(Base):
    __tablename__ = "stores"

    __table_args__ = (
        CheckConstraint(
            "store_type IS NULL OR store_type IN ('a', 'b', 'c', 'd')",
            name="chk_store_type",
        ),
        CheckConstraint(
            "assortment IS NULL OR assortment IN ('a', 'b', 'c')",
            name="chk_assortment",
        ),
        CheckConstraint(
            "competition_distance IS NULL OR competition_distance >= 0",
            name="chk_competition_distance",
        ),
    )

    store_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    store_type: Mapped[str | None] = mapped_column(String(1))
    assortment: Mapped[str | None] = mapped_column(String(1))

    competition_distance: Mapped[int | None] = mapped_column(Integer)
    competition_open_since_month: Mapped[int | None] = mapped_column(Integer)
    competition_open_since_year: Mapped[int | None] = mapped_column(Integer)

    promo2: Mapped[bool | None] = mapped_column(Boolean)
    promo2_since_week: Mapped[int | None] = mapped_column(Integer)
    promo2_since_year: Mapped[int | None] = mapped_column(Integer)
    promo_interval: Mapped[str | None] = mapped_column(String(100))

    metadata_import_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("dataset_imports.id"),
    )


class DailyStoreSale(Base):
    __tablename__ = "daily_store_sales"

    __table_args__ = (
        CheckConstraint("day_of_week BETWEEN 1 AND 7", name="chk_day_of_week"),
        CheckConstraint("sales >= 0", name="chk_sales"),
        CheckConstraint("customers >= 0", name="chk_customers"),
        CheckConstraint(
            "state_holiday IN ('0', 'a', 'b', 'c')",
            name="chk_state_holiday",
        ),
        Index("idx_daily_sales_date", "sales_date"),
        Index("idx_daily_sales_store_date", "store_id", "sales_date"),
        Index("idx_daily_sales_promo", "promo"),
    )

    store_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("stores.store_id"),
        primary_key=True,
    )
    sales_date: Mapped[date] = mapped_column(Date, primary_key=True)
    day_of_week: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    sales: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    customers: Mapped[int] = mapped_column(Integer, nullable=False)
    is_open: Mapped[bool] = mapped_column(Boolean, nullable=False)
    promo: Mapped[bool] = mapped_column(Boolean, nullable=False)
    state_holiday: Mapped[str] = mapped_column(
        String(1), nullable=False, server_default=text("'0'")
    )
    school_holiday: Mapped[bool] = mapped_column(Boolean, nullable=False)

    import_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("dataset_imports.id"),
        nullable=False,
    )
    source_row_number: Mapped[int | None] = mapped_column(Integer)


class DatasetImportError(Base):
    __tablename__ = "dataset_import_errors"

    id: Mapped[int] = mapped_column(
        BigInteger,
        Identity(always=True),
        primary_key=True,
    )
    import_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("dataset_imports.id"),
        nullable=False,
    )
    source_row_number: Mapped[int | None] = mapped_column(Integer)
    raw_record: Mapped[dict | None] = mapped_column(JSONB)
    error_message: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("NOW()"),
    )


class AuditLog(Base):
    __tablename__ = "audit_logs"

    __table_args__ = (
        Index("idx_audit_entity", "entity_name", "entity_id"),
        Index("idx_audit_logs_org_id", "organisation_id"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        Identity(always=True),
        primary_key=True,
    )
    organisation_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("organisations.id"),
        nullable=True,
    )
    actor_type: Mapped[str | None] = mapped_column(String(50))
    actor_ref: Mapped[str | None] = mapped_column(String(100))
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_name: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_id: Mapped[str | None] = mapped_column(String(100))
    details: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("NOW()"),
    )
