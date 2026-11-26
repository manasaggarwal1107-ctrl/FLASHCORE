
from sqlalchemy import (
    BigInteger, String, Text, Integer, Numeric,
    ForeignKey, CheckConstraint, UniqueConstraint,
    TIMESTAMP, text
)
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime

from app.core.database import Base


class FlashSale(Base):
    __tablename__ = "flash_sales"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)

    starts_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False
    )
    ends_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False
    )

    status: Mapped[str] = mapped_column(
        String(20), default="draft",
        server_default=text("'draft'"), nullable=False
    )
    origin: Mapped[str] = mapped_column(
        String(20), default="manual",
        server_default=text("'manual'"), nullable=False
    )
    created_at = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("NOW()")
    )


class FlashSaleProduct(Base):
    __tablename__ = "flash_sale_products"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    flash_sale_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("flash_sales.id"), nullable=False
    )
    product_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("products.id"), nullable=False
    )
    sale_price: Mapped[float] = mapped_column(
        Numeric(12, 2), nullable=False
    )
    allocated_quantity: Mapped[int] = mapped_column(
        Integer, nullable=False
    )
    sold_quantity: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0"
    )
    created_at = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("NOW()")
    )

