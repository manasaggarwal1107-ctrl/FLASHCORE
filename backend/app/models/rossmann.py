
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Integer,
    SmallInteger,
    String,
    Boolean,
    Date,
    Numeric,
    ForeignKey,
    Text,
    TIMESTAMP,
    JSON,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class DatasetImport(Base):
    __tablename__ = "dataset_imports"

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True
    )
    source_name: Mapped[str] = mapped_column(
        String(150), nullable=False
    )
    source_url: Mapped[str | None] = mapped_column(Text)
    source_file: Mapped[str] = mapped_column(
        String(255), nullable=False
    )
    source_split: Mapped[str] = mapped_column(
        String(30), nullable=False
    )
    checksum_sha256: Mapped[str | None] = mapped_column(
        String(64)
    )
    imported_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=text("NOW()")
    )
    total_rows: Mapped[int] = mapped_column(
        Integer, nullable=False
    )
    successful_rows: Mapped[int] = mapped_column(
        Integer, nullable=False
    )
    rejected_rows: Mapped[int] = mapped_column(
        Integer, nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False
    )


class Store(Base):
    __tablename__ = "stores"

    store_id: Mapped[int] = mapped_column(
        Integer, primary_key=True
    )
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
        ForeignKey("dataset_imports.id")
    )


class DailyStoreSale(Base):
    __tablename__ = "daily_store_sales"

    store_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("stores.store_id"),
        primary_key=True
    )
    sales_date: Mapped[date] = mapped_column(
        Date, primary_key=True
    )
    day_of_week: Mapped[int] = mapped_column(SmallInteger)
    sales: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    customers: Mapped[int] = mapped_column(Integer)
    is_open: Mapped[bool] = mapped_column(Boolean)
    promo: Mapped[bool] = mapped_column(Boolean)
    state_holiday: Mapped[str] = mapped_column(String(1))
    school_holiday: Mapped[bool] = mapped_column(Boolean)

    import_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("dataset_imports.id")
    )
    source_row_number: Mapped[int | None] = mapped_column(Integer)


class DatasetImportError(Base):
    __tablename__ = "dataset_import_errors"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    import_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("dataset_imports.id"), nullable=False
    )
    source_row_number: Mapped[int | None] = mapped_column(Integer)
    raw_record: Mapped[dict | None] = mapped_column(JSON)
    error_message: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("NOW()")
    )


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    actor_type: Mapped[str | None] = mapped_column(String(50))
    actor_ref: Mapped[str | None] = mapped_column(String(200))
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_name: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_id: Mapped[str | None] = mapped_column(String(100))
    details: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("NOW()")
    )
