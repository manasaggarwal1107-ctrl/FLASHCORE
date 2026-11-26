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


class CommerceProduct(Base):
    __tablename__ = "commerce_products"

    __table_args__ = (
        UniqueConstraint(
            "organisation_id",
            "sku",
            name="uq_commerce_products_org_sku",
        ),
        CheckConstraint(
            "status IN ('draft', 'active', 'archived')",
            name="chk_commerce_products_status",
        ),
        CheckConstraint("price_minor >= 0", name="chk_commerce_products_price"),
        CheckConstraint(
            "char_length(currency) = 3",
            name="chk_commerce_products_currency",
        ),
        CheckConstraint(
            "tax_rate_bps >= 0 AND tax_rate_bps <= 10000",
            name="chk_commerce_products_tax_rate",
        ),
        Index("idx_commerce_products_org_id", "organisation_id"),
        Index("idx_commerce_products_org_status", "organisation_id", "status"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger, Identity(always=True), primary_key=True
    )
    organisation_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("organisations.id"), nullable=False
    )
    sku: Mapped[str] = mapped_column(String(80), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    category: Mapped[str | None] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'draft'")
    )
    price_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(
        String(3), nullable=False, server_default=text("'INR'")
    )
    tax_rate_bps: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    metadata_json: Mapped[dict | None] = mapped_column("metadata", JSONB)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("NOW()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("NOW()"),
        onupdate=func.now(),
    )


class InventoryLocation(Base):
    __tablename__ = "inventory_locations"

    __table_args__ = (
        UniqueConstraint(
            "organisation_id",
            "code",
            name="uq_inventory_locations_org_code",
        ),
        CheckConstraint(
            "location_type IN ('warehouse', 'store', 'fulfilment_centre')",
            name="chk_inventory_locations_type",
        ),
        Index("idx_inventory_locations_org_id", "organisation_id"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger, Identity(always=True), primary_key=True
    )
    organisation_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("organisations.id"), nullable=False
    )
    code: Mapped[str] = mapped_column(String(60), nullable=False)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    location_type: Mapped[str] = mapped_column(
        String(30), nullable=False, server_default=text("'warehouse'")
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("TRUE")
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


class InventoryBalance(Base):
    __tablename__ = "inventory_balances"

    __table_args__ = (
        UniqueConstraint(
            "organisation_id",
            "product_id",
            "location_id",
            name="uq_inventory_balances_org_prod_loc",
        ),
        CheckConstraint("quantity >= 0", name="chk_inventory_balances_quantity"),
        CheckConstraint(
            "reserved_quantity >= 0",
            name="chk_inventory_balances_reserved",
        ),
        CheckConstraint(
            "reserved_quantity <= quantity",
            name="chk_inventory_balances_invariant",
        ),
        CheckConstraint(
            "low_stock_threshold >= 0",
            name="chk_inventory_balances_threshold",
        ),
        Index("idx_inventory_balances_org_id", "organisation_id"),
        Index("idx_inventory_balances_product_id", "product_id"),
        Index("idx_inventory_balances_location_id", "location_id"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger, Identity(always=True), primary_key=True
    )
    organisation_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("organisations.id"), nullable=False
    )
    product_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("commerce_products.id"), nullable=False
    )
    location_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("inventory_locations.id"), nullable=False
    )
    quantity: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    reserved_quantity: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    low_stock_threshold: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("5")
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("NOW()"),
        onupdate=func.now(),
    )


class InventoryMovement(Base):
    __tablename__ = "inventory_movements"

    __table_args__ = (
        CheckConstraint(
            "movement_type IN ('adjustment', 'reservation', 'release', 'expiry', 'fulfilment', 'sale')",
            name="chk_inventory_movements_type",
        ),
        CheckConstraint(
            "balance_after >= 0 AND reserved_after >= 0",
            name="chk_inventory_movements_balances",
        ),
        Index("idx_inventory_movements_org_id", "organisation_id"),
        Index("idx_inventory_movements_balance_id", "balance_id"),
        Index("idx_inventory_movements_created_at", "created_at"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger, Identity(always=True), primary_key=True
    )
    organisation_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("organisations.id"), nullable=False
    )
    balance_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("inventory_balances.id"), nullable=False
    )
    product_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("commerce_products.id"), nullable=False
    )
    location_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("inventory_locations.id"), nullable=False
    )
    movement_type: Mapped[str] = mapped_column(String(30), nullable=False)
    quantity_delta: Mapped[int] = mapped_column(Integer, nullable=False)
    reserved_delta: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    balance_after: Mapped[int] = mapped_column(Integer, nullable=False)
    reserved_after: Mapped[int] = mapped_column(Integer, nullable=False)
    reference_type: Mapped[str | None] = mapped_column(String(60))
    reference_id: Mapped[str | None] = mapped_column(String(100))
    reason: Mapped[str | None] = mapped_column(Text)
    actor_ref: Mapped[str | None] = mapped_column(String(150))
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("NOW()")
    )


class Customer(Base):
    __tablename__ = "customers"

    __table_args__ = (
        CheckConstraint(
            "status IN ('active', 'inactive')",
            name="chk_customers_status",
        ),
        Index(
            "uq_customers_org_email_lower",
            "organisation_id",
            text("LOWER(email)"),
            unique=True,
            postgresql_where=text("email IS NOT NULL"),
        ),
        Index("idx_customers_org_id", "organisation_id"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger, Identity(always=True), primary_key=True
    )
    organisation_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("organisations.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    email: Mapped[str | None] = mapped_column(String(320))
    phone: Mapped[str | None] = mapped_column(String(30))
    billing_address: Mapped[dict | None] = mapped_column(JSONB)
    shipping_address: Mapped[dict | None] = mapped_column(JSONB)
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


class Order(Base):
    __tablename__ = "orders"

    __table_args__ = (
        UniqueConstraint(
            "organisation_id",
            "order_number",
            name="uq_orders_org_number",
        ),
        CheckConstraint("subtotal_minor >= 0", name="chk_orders_subtotal"),
        CheckConstraint("discount_minor >= 0", name="chk_orders_discount"),
        CheckConstraint("tax_minor >= 0", name="chk_orders_tax"),
        CheckConstraint("total_minor >= 0", name="chk_orders_total"),
        CheckConstraint(
            "order_status IN ('DRAFT', 'PENDING_PAYMENT', 'PAID', 'PROCESSING', 'FULFILLED', 'CANCELLED', 'EXPIRED')",
            name="chk_orders_order_status",
        ),
        CheckConstraint(
            "payment_status IN ('UNPAID', 'CREATED', 'PENDING', 'AUTHORIZED', 'CAPTURED', 'FAILED', 'CANCELLED')",
            name="chk_orders_payment_status",
        ),
        Index(
            "uq_orders_org_idempotency",
            "organisation_id",
            "idempotency_key",
            unique=True,
            postgresql_where=text("idempotency_key IS NOT NULL"),
        ),
        Index("idx_orders_org_id", "organisation_id"),
        Index("idx_orders_customer_id", "customer_id"),
        Index("idx_orders_org_status", "organisation_id", "order_status"),
        Index("idx_orders_placed_at", "placed_at"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger, Identity(always=True), primary_key=True
    )
    organisation_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("organisations.id"), nullable=False
    )
    customer_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("customers.id")
    )
    order_number: Mapped[str] = mapped_column(String(60), nullable=False)
    idempotency_key: Mapped[str | None] = mapped_column(String(128))
    currency: Mapped[str] = mapped_column(
        String(3), nullable=False, server_default=text("'INR'")
    )
    subtotal_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    discount_minor: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default=text("0")
    )
    tax_minor: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default=text("0")
    )
    total_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    order_status: Mapped[str] = mapped_column(
        String(30), nullable=False, server_default=text("'DRAFT'")
    )
    payment_status: Mapped[str] = mapped_column(
        String(30), nullable=False, server_default=text("'UNPAID'")
    )
    customer_snapshot: Mapped[dict | None] = mapped_column(JSONB)
    reservation_expires_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True)
    )
    placed_at: Mapped[datetime] = mapped_column(
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


class OrderItem(Base):
    __tablename__ = "order_items"

    __table_args__ = (
        CheckConstraint("quantity > 0", name="chk_order_items_quantity"),
        CheckConstraint("unit_price_minor >= 0", name="chk_order_items_unit_price"),
        CheckConstraint("tax_minor >= 0", name="chk_order_items_tax"),
        CheckConstraint("line_total_minor >= 0", name="chk_order_items_total"),
        Index("idx_order_items_org_id", "organisation_id"),
        Index("idx_order_items_order_id", "order_id"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger, Identity(always=True), primary_key=True
    )
    organisation_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("organisations.id"), nullable=False
    )
    order_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False
    )
    product_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("commerce_products.id"), nullable=False
    )
    location_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("inventory_locations.id"), nullable=False
    )
    sku_snapshot: Mapped[str] = mapped_column(String(80), nullable=False)
    name_snapshot: Mapped[str] = mapped_column(String(200), nullable=False)
    unit_price_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    tax_rate_bps: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    tax_minor: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default=text("0")
    )
    line_total_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)


class InventoryReservation(Base):
    __tablename__ = "inventory_reservations"

    __table_args__ = (
        CheckConstraint("quantity > 0", name="chk_inventory_reservations_quantity"),
        CheckConstraint(
            "status IN ('PENDING', 'CONFIRMED', 'RELEASED', 'EXPIRED')",
            name="chk_inventory_reservations_status",
        ),
        Index(
            "idx_inventory_reservations_org_status_exp",
            "organisation_id",
            "status",
            "expires_at",
        ),
        Index("idx_inventory_reservations_order_id", "order_id"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger, Identity(always=True), primary_key=True
    )
    organisation_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("organisations.id"), nullable=False
    )
    order_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False
    )
    order_item_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("order_items.id", ondelete="CASCADE"), nullable=False
    )
    balance_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("inventory_balances.id"), nullable=False
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'PENDING'")
    )
    expires_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False
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


class OrderEvent(Base):
    __tablename__ = "order_events"

    __table_args__ = (
        Index("idx_order_events_org_id", "organisation_id"),
        Index("idx_order_events_order_id", "order_id"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger, Identity(always=True), primary_key=True
    )
    organisation_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("organisations.id"), nullable=False
    )
    order_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False
    )
    from_status: Mapped[str | None] = mapped_column(String(30))
    to_status: Mapped[str] = mapped_column(String(30), nullable=False)
    event_type: Mapped[str] = mapped_column(String(60), nullable=False)
    actor_ref: Mapped[str | None] = mapped_column(String(150))
    details: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("NOW()")
    )
