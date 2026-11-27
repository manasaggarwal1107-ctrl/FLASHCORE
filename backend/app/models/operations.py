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


class SalesRecord(Base):
    __tablename__ = "sales_records"

    __table_args__ = (
        UniqueConstraint(
            "organisation_id",
            "order_id",
            name="uq_sales_records_org_order",
        ),
        UniqueConstraint(
            "organisation_id",
            "transaction_ref",
            name="uq_sales_records_org_tx_ref",
        ),
        CheckConstraint(
            "gross_amount_minor >= 0 AND discount_minor >= 0 AND tax_minor >= 0 AND net_amount_minor >= 0 AND refunded_minor >= 0",
            name="chk_sales_records_amounts",
        ),
        CheckConstraint(
            "refund_status IN ('NONE', 'PARTIAL', 'FULL')",
            name="chk_sales_records_refund_status",
        ),
        Index("idx_sales_records_org_id", "organisation_id"),
        Index("idx_sales_records_org_sold_at", "organisation_id", "sold_at"),
        Index("idx_sales_records_campaign_id", "campaign_id"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger, Identity(always=True), primary_key=True
    )
    organisation_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("organisations.id"), nullable=False
    )
    transaction_ref: Mapped[str] = mapped_column(String(80), nullable=False)
    order_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False
    )
    order_number: Mapped[str] = mapped_column(String(60), nullable=False)
    customer_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("customers.id")
    )
    customer_name: Mapped[str | None] = mapped_column(String(150))
    location_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("inventory_locations.id")
    )
    campaign_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("surge_campaigns.id")
    )
    gross_amount_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    discount_minor: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default=text("0")
    )
    tax_minor: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default=text("0")
    )
    net_amount_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    refunded_minor: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default=text("0")
    )
    currency: Mapped[str] = mapped_column(
        String(3), nullable=False, server_default=text("'INR'")
    )
    payment_status: Mapped[str] = mapped_column(String(30), nullable=False)
    refund_status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'NONE'")
    )
    sold_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("NOW()")
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


class OrderReturn(Base):
    __tablename__ = "order_returns"

    __table_args__ = (
        UniqueConstraint(
            "organisation_id",
            "return_number",
            name="uq_order_returns_org_number",
        ),
        CheckConstraint(
            "return_type IN ('return', 'exchange')",
            name="chk_order_returns_type",
        ),
        CheckConstraint(
            "status IN ('REQUESTED', 'APPROVED', 'REJECTED', 'COMPLETED')",
            name="chk_order_returns_status",
        ),
        CheckConstraint(
            "condition IN ('unopened', 'good', 'damaged', 'defective')",
            name="chk_order_returns_condition",
        ),
        CheckConstraint(
            "refund_amount_minor >= 0",
            name="chk_order_returns_refund_amount",
        ),
        Index("idx_order_returns_org_id", "organisation_id"),
        Index("idx_order_returns_order_id", "order_id"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger, Identity(always=True), primary_key=True
    )
    organisation_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("organisations.id"), nullable=False
    )
    return_number: Mapped[str] = mapped_column(String(60), nullable=False)
    order_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("orders.id"), nullable=False
    )
    customer_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("customers.id")
    )
    return_type: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'return'")
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'REQUESTED'")
    )
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    condition: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'good'")
    )
    restock_approved: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("FALSE")
    )
    refund_amount_minor: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default=text("0")
    )
    refund_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("payment_refunds.id")
    )
    exchange_order_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("orders.id")
    )
    requested_by: Mapped[str] = mapped_column(String(150), nullable=False)
    reviewed_by: Mapped[str | None] = mapped_column(String(150))
    reviewed_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("NOW()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("NOW()"),
        onupdate=func.now(),
    )


class OrderReturnItem(Base):
    __tablename__ = "order_return_items"

    __table_args__ = (
        CheckConstraint("quantity > 0", name="chk_order_return_items_quantity"),
        CheckConstraint(
            "condition IN ('unopened', 'good', 'damaged', 'defective')",
            name="chk_order_return_items_condition",
        ),
        Index("idx_order_return_items_org_id", "organisation_id"),
        Index("idx_order_return_items_return_id", "return_id"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger, Identity(always=True), primary_key=True
    )
    organisation_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("organisations.id"), nullable=False
    )
    return_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("order_returns.id", ondelete="CASCADE"), nullable=False
    )
    order_item_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("order_items.id"), nullable=False
    )
    product_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("commerce_products.id"), nullable=False
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    condition: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'good'")
    )
    restocked: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("FALSE")
    )


class Notification(Base):
    __tablename__ = "notifications"

    __table_args__ = (
        CheckConstraint(
            "category IN ('low_stock', 'pending_order', 'campaign', 'refund', 'purchase_order', 'return', 'system')",
            name="chk_notifications_category",
        ),
        CheckConstraint(
            "severity IN ('info', 'warning', 'critical')",
            name="chk_notifications_severity",
        ),
        Index("idx_notifications_org_id", "organisation_id"),
        Index("idx_notifications_org_unread", "organisation_id", "is_read", "created_at"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger, Identity(always=True), primary_key=True
    )
    organisation_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("organisations.id"), nullable=False
    )
    category: Mapped[str] = mapped_column(String(30), nullable=False)
    severity: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'info'")
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    entity_type: Mapped[str | None] = mapped_column(String(60))
    entity_id: Mapped[str | None] = mapped_column(String(100))
    dedupe_key: Mapped[str | None] = mapped_column(String(160))
    metadata_json: Mapped[dict | None] = mapped_column("metadata", JSONB)
    is_read: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("FALSE")
    )
    read_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("NOW()")
    )
