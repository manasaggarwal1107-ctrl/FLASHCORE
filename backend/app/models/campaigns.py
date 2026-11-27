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


class SurgeCampaign(Base):
    __tablename__ = "surge_campaigns"

    __table_args__ = (
        CheckConstraint(
            "status IN ('DRAFT', 'SCHEDULED', 'ACTIVE', 'PAUSED', 'COMPLETED', 'CANCELLED')",
            name="chk_surge_campaigns_status",
        ),
        CheckConstraint(
            "discount_type IN ('percentage', 'fixed')",
            name="chk_surge_campaigns_discount_type",
        ),
        CheckConstraint(
            "discount_value > 0",
            name="chk_surge_campaigns_discount_value",
        ),
        CheckConstraint(
            "ends_at > starts_at",
            name="chk_surge_campaigns_window",
        ),
        CheckConstraint(
            "campaign_limit_units IS NULL OR campaign_limit_units > 0",
            name="chk_surge_campaigns_limit",
        ),
        CheckConstraint(
            "per_customer_limit IS NULL OR per_customer_limit > 0",
            name="chk_surge_campaigns_per_customer",
        ),
        CheckConstraint(
            "total_units_sold >= 0",
            name="chk_surge_campaigns_sold",
        ),
        Index("idx_surge_campaigns_org_id", "organisation_id"),
        Index("idx_surge_campaigns_org_status", "organisation_id", "status"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger, Identity(always=True), primary_key=True
    )
    organisation_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("organisations.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'DRAFT'")
    )
    starts_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False
    )
    ends_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False
    )
    discount_type: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'percentage'")
    )
    discount_value: Mapped[int] = mapped_column(BigInteger, nullable=False)
    category_filter: Mapped[str | None] = mapped_column(String(120))
    campaign_limit_units: Mapped[int | None] = mapped_column(Integer)
    total_units_sold: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    per_customer_limit: Mapped[int | None] = mapped_column(Integer)
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


class SurgeCampaignProduct(Base):
    __tablename__ = "surge_campaign_products"

    __table_args__ = (
        UniqueConstraint(
            "campaign_id",
            "product_id",
            name="uq_surge_campaign_products_campaign_product",
        ),
        CheckConstraint(
            "original_price_minor >= 0 AND sale_price_minor >= 0",
            name="chk_surge_campaign_products_prices",
        ),
        CheckConstraint(
            "allocated_units > 0",
            name="chk_surge_campaign_products_allocated",
        ),
        CheckConstraint(
            "sold_units >= 0 AND sold_units <= allocated_units",
            name="chk_surge_campaign_products_sold",
        ),
        Index("idx_surge_campaign_products_org_id", "organisation_id"),
        Index("idx_surge_campaign_products_campaign_id", "campaign_id"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger, Identity(always=True), primary_key=True
    )
    organisation_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("organisations.id"), nullable=False
    )
    campaign_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("surge_campaigns.id", ondelete="CASCADE"), nullable=False
    )
    product_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("commerce_products.id"), nullable=False
    )
    original_price_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sale_price_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    allocated_units: Mapped[int] = mapped_column(Integer, nullable=False)
    sold_units: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )


class Promotion(Base):
    __tablename__ = "promotions"

    __table_args__ = (
        UniqueConstraint(
            "organisation_id",
            "code",
            name="uq_promotions_org_code",
        ),
        CheckConstraint(
            "discount_type IN ('percentage', 'fixed')",
            name="chk_promotions_discount_type",
        ),
        CheckConstraint("discount_value > 0", name="chk_promotions_discount_value"),
        CheckConstraint("min_order_minor >= 0", name="chk_promotions_min_order"),
        CheckConstraint(
            "max_discount_minor IS NULL OR max_discount_minor >= 0",
            name="chk_promotions_max_discount",
        ),
        CheckConstraint(
            "usage_limit IS NULL OR usage_limit > 0",
            name="chk_promotions_usage_limit",
        ),
        CheckConstraint(
            "used_count >= 0",
            name="chk_promotions_used_count",
        ),
        Index("idx_promotions_org_id", "organisation_id"),
        Index("idx_promotions_org_active", "organisation_id", "is_active"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger, Identity(always=True), primary_key=True
    )
    organisation_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("organisations.id"), nullable=False
    )
    code: Mapped[str] = mapped_column(String(60), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    discount_type: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'percentage'")
    )
    discount_value: Mapped[int] = mapped_column(BigInteger, nullable=False)
    min_order_minor: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default=text("0")
    )
    max_discount_minor: Mapped[int | None] = mapped_column(BigInteger)
    usage_limit: Mapped[int | None] = mapped_column(Integer)
    used_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    per_customer_limit: Mapped[int | None] = mapped_column(Integer)
    customer_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("customers.id")
    )
    starts_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    ends_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
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


class PromotionRedemption(Base):
    __tablename__ = "promotion_redemptions"

    __table_args__ = (
        UniqueConstraint(
            "promotion_id",
            "order_id",
            name="uq_promotion_redemptions_promo_order",
        ),
        CheckConstraint(
            "discount_minor >= 0",
            name="chk_promotion_redemptions_discount",
        ),
        Index("idx_promotion_redemptions_org_id", "organisation_id"),
        Index("idx_promotion_redemptions_promo_cust", "promotion_id", "customer_id"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger, Identity(always=True), primary_key=True
    )
    organisation_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("organisations.id"), nullable=False
    )
    promotion_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("promotions.id", ondelete="CASCADE"), nullable=False
    )
    order_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False
    )
    customer_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("customers.id")
    )
    discount_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("NOW()")
    )
