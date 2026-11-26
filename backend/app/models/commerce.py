from sqlalchemy import (
    BigInteger, String, Text, Boolean, Integer,
    Numeric, ForeignKey, CheckConstraint, UniqueConstraint,
    TIMESTAMP, text
)
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    parent_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("categories.id")
    )
    created_at = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("NOW()")
    )


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    category_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("categories.id")
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    sku: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    price: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)


    currency: Mapped[str] = mapped_column(
        String(3), default="INR", server_default=text("'INR'")
    )

    origin: Mapped[str] = mapped_column(
        String(20), default="manual", server_default=text("'manual'")
    )


    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default=text("TRUE")
    )
    created_at = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("NOW()")
    )


class Inventory(Base):
    __tablename__ = "inventory"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    product_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("products.id"), unique=True, nullable=False
    )
    quantity: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0"
    )
    reserved_quantity: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0"
    )
    low_stock_threshold: Mapped[int] = mapped_column(
        Integer, default=5, server_default="5"
    )
    updated_at = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=text("NOW()"),
        onupdate=text("NOW()")
    )