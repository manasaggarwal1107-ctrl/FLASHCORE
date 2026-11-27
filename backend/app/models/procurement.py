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
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class StockTransfer(Base):
    __tablename__ = "stock_transfers"

    __table_args__ = (
        UniqueConstraint(
            "organisation_id",
            "transfer_number",
            name="uq_stock_transfers_org_number",
        ),
        CheckConstraint("quantity > 0", name="chk_stock_transfers_quantity"),
        CheckConstraint(
            "from_location_id <> to_location_id",
            name="chk_stock_transfers_distinct_locations",
        ),
        CheckConstraint(
            "status IN ('DRAFT', 'PENDING_APPROVAL', 'APPROVED', 'IN_TRANSIT', 'RECEIVED', 'CANCELLED')",
            name="chk_stock_transfers_status",
        ),
        Index("idx_stock_transfers_org_id", "organisation_id"),
        Index("idx_stock_transfers_org_status", "organisation_id", "status"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger, Identity(always=True), primary_key=True
    )
    organisation_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("organisations.id"), nullable=False
    )
    transfer_number: Mapped[str] = mapped_column(String(60), nullable=False)
    product_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("commerce_products.id"), nullable=False
    )
    from_location_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("inventory_locations.id"), nullable=False
    )
    to_location_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("inventory_locations.id"), nullable=False
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, server_default=text("'DRAFT'")
    )
    requires_approval: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("FALSE")
    )
    notes: Mapped[str | None] = mapped_column(Text)
    requested_by: Mapped[str] = mapped_column(String(150), nullable=False)
    approved_by: Mapped[str | None] = mapped_column(String(150))
    dispatched_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    received_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("NOW()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("NOW()"),
        onupdate=func.now(),
    )


class Supplier(Base):
    __tablename__ = "suppliers"

    __table_args__ = (
        UniqueConstraint(
            "organisation_id", "code", name="uq_suppliers_org_code"
        ),
        CheckConstraint(
            "status IN ('active', 'inactive')", name="chk_suppliers_status"
        ),
        Index("idx_suppliers_org_id", "organisation_id"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger, Identity(always=True), primary_key=True
    )
    organisation_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("organisations.id"), nullable=False
    )
    code: Mapped[str] = mapped_column(String(60), nullable=False)
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    contact_name: Mapped[str | None] = mapped_column(String(150))
    email: Mapped[str | None] = mapped_column(String(320))
    phone: Mapped[str | None] = mapped_column(String(40))
    gstin: Mapped[str | None] = mapped_column(String(20))
    state_code: Mapped[str | None] = mapped_column(String(4))
    outstanding_payable_minor: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default=text("0")
    )
    address: Mapped[str | None] = mapped_column(Text)
    payment_terms: Mapped[str | None] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'active'")
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


class PurchaseOrder(Base):
    __tablename__ = "purchase_orders"

    __table_args__ = (
        UniqueConstraint(
            "organisation_id",
            "po_number",
            name="uq_purchase_orders_org_number",
        ),
        CheckConstraint(
            "total_cost_minor >= 0", name="chk_purchase_orders_total_cost"
        ),
        CheckConstraint(
            "status IN ('DRAFT', 'SUBMITTED', 'PARTIALLY_RECEIVED', 'COMPLETED', 'CANCELLED')",
            name="chk_purchase_orders_status",
        ),
        CheckConstraint(
            "char_length(currency) = 3",
            name="chk_purchase_orders_currency",
        ),
        Index("idx_purchase_orders_org_id", "organisation_id"),
        Index("idx_purchase_orders_supplier_id", "supplier_id"),
        Index("idx_purchase_orders_org_status", "organisation_id", "status"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger, Identity(always=True), primary_key=True
    )
    organisation_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("organisations.id"), nullable=False
    )
    po_number: Mapped[str] = mapped_column(String(60), nullable=False)
    supplier_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("suppliers.id"), nullable=False
    )
    location_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("inventory_locations.id"), nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, server_default=text("'DRAFT'")
    )
    currency: Mapped[str] = mapped_column(
        String(3), nullable=False, server_default=text("'INR'")
    )
    total_cost_minor: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default=text("0")
    )
    expected_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    submitted_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    received_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    notes: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[str] = mapped_column(String(150), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("NOW()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("NOW()"),
        onupdate=func.now(),
    )


class PurchaseOrderItem(Base):
    __tablename__ = "purchase_order_items"

    __table_args__ = (
        CheckConstraint(
            "ordered_quantity > 0",
            name="chk_purchase_order_items_ordered",
        ),
        CheckConstraint(
            "received_quantity >= 0 AND received_quantity <= ordered_quantity",
            name="chk_purchase_order_items_received",
        ),
        CheckConstraint(
            "unit_cost_minor >= 0",
            name="chk_purchase_order_items_unit_cost",
        ),
        CheckConstraint(
            "line_total_minor >= 0",
            name="chk_purchase_order_items_line_total",
        ),
        Index("idx_purchase_order_items_org_id", "organisation_id"),
        Index("idx_purchase_order_items_po_id", "purchase_order_id"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger, Identity(always=True), primary_key=True
    )
    organisation_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("organisations.id"), nullable=False
    )
    purchase_order_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("purchase_orders.id", ondelete="CASCADE"), nullable=False
    )
    product_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("commerce_products.id"), nullable=False
    )
    ordered_quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    received_quantity: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    unit_cost_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    line_total_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
