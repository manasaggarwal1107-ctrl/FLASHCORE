from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    ForeignKey,
    Identity,
    Index,
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


class PaymentProviderAccount(Base):
    __tablename__ = "payment_provider_accounts"

    __table_args__ = (
        UniqueConstraint(
            "organisation_id",
            "provider",
            "mode",
            name="uq_payment_accounts_org_provider_mode",
        ),
        UniqueConstraint("key_id", name="uq_payment_accounts_key_id"),
        CheckConstraint(
            "provider IN ('razorpay')",
            name="chk_payment_accounts_provider",
        ),
        CheckConstraint(
            "mode IN ('test', 'live')",
            name="chk_payment_accounts_mode",
        ),
        CheckConstraint(
            "status IN ('active', 'disabled')",
            name="chk_payment_accounts_status",
        ),
        Index("idx_payment_accounts_org_id", "organisation_id"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger, Identity(always=True), primary_key=True
    )
    organisation_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("organisations.id"), nullable=False
    )
    provider: Mapped[str] = mapped_column(String(30), nullable=False)
    mode: Mapped[str] = mapped_column(
        String(10), nullable=False, server_default=text("'test'")
    )
    key_id: Mapped[str] = mapped_column(String(120), nullable=False)
    encrypted_key_secret: Mapped[str] = mapped_column(Text, nullable=False)
    encrypted_webhook_secret: Mapped[str] = mapped_column(Text, nullable=False)
    key_version: Mapped[str] = mapped_column(
        String(40), nullable=False, server_default=text("'v1'")
    )
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


class PaymentOrder(Base):
    __tablename__ = "payment_orders"

    __table_args__ = (
        UniqueConstraint(
            "provider",
            "provider_order_id",
            name="uq_payment_orders_provider_order_id",
        ),
        CheckConstraint("amount_minor > 0", name="chk_payment_orders_amount"),
        CheckConstraint(
            "status IN ('CREATED', 'PENDING', 'AUTHORIZED', 'CAPTURED', 'FAILED', 'CANCELLED')",
            name="chk_payment_orders_status",
        ),
        Index(
            "uq_payment_orders_org_idempotency",
            "organisation_id",
            "idempotency_key",
            unique=True,
            postgresql_where=text("idempotency_key IS NOT NULL"),
        ),
        Index("idx_payment_orders_org_id", "organisation_id"),
        Index("idx_payment_orders_order_id", "order_id"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger, Identity(always=True), primary_key=True
    )
    organisation_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("organisations.id"), nullable=False
    )
    order_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("orders.id"), nullable=False
    )
    provider_account_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("payment_provider_accounts.id"), nullable=False
    )
    provider: Mapped[str] = mapped_column(String(30), nullable=False)
    provider_order_id: Mapped[str] = mapped_column(String(120), nullable=False)
    idempotency_key: Mapped[str | None] = mapped_column(String(128))
    amount_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(
        String(3), nullable=False, server_default=text("'INR'")
    )
    receipt: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'CREATED'")
    )
    provider_payload: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("NOW()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("NOW()"),
        onupdate=func.now(),
    )


class PaymentAttempt(Base):
    __tablename__ = "payment_attempts"

    __table_args__ = (
        CheckConstraint(
            "status IN ('CREATED', 'PENDING', 'AUTHORIZED', 'CAPTURED', 'FAILED', 'CANCELLED')",
            name="chk_payment_attempts_status",
        ),
        Index(
            "uq_payment_attempts_provider_payment_id",
            "provider",
            "provider_payment_id",
            unique=True,
            postgresql_where=text("provider_payment_id IS NOT NULL"),
        ),
        Index("idx_payment_attempts_org_id", "organisation_id"),
        Index("idx_payment_attempts_payment_order_id", "payment_order_id"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger, Identity(always=True), primary_key=True
    )
    organisation_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("organisations.id"), nullable=False
    )
    payment_order_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("payment_orders.id"), nullable=False
    )
    order_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("orders.id"), nullable=False
    )
    provider: Mapped[str] = mapped_column(String(30), nullable=False)
    provider_payment_id: Mapped[str | None] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'CREATED'")
    )
    failure_code: Mapped[str | None] = mapped_column(String(80))
    failure_reason: Mapped[str | None] = mapped_column(Text)
    signature_verified: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("FALSE")
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


class PaymentTransaction(Base):
    __tablename__ = "payment_transactions"

    __table_args__ = (
        UniqueConstraint(
            "provider",
            "provider_payment_id",
            "event_type",
            name="uq_payment_transactions_provider_event",
        ),
        CheckConstraint(
            "event_type IN ('AUTHORIZED', 'CAPTURED', 'FAILED', 'CANCELLED')",
            name="chk_payment_transactions_event_type",
        ),
        CheckConstraint("amount_minor >= 0", name="chk_payment_transactions_amount"),
        CheckConstraint(
            "status IN ('CREATED', 'PENDING', 'AUTHORIZED', 'CAPTURED', 'FAILED', 'CANCELLED')",
            name="chk_payment_transactions_status",
        ),
        CheckConstraint(
            "source IN ('checkout_verify', 'webhook')",
            name="chk_payment_transactions_source",
        ),
        Index("idx_payment_transactions_org_id", "organisation_id"),
        Index("idx_payment_transactions_order_id", "order_id"),
        Index("idx_payment_transactions_created_at", "created_at"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger, Identity(always=True), primary_key=True
    )
    organisation_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("organisations.id"), nullable=False
    )
    order_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("orders.id"), nullable=False
    )
    payment_order_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("payment_orders.id"), nullable=False
    )
    payment_attempt_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("payment_attempts.id")
    )
    provider: Mapped[str] = mapped_column(String(30), nullable=False)
    provider_payment_id: Mapped[str] = mapped_column(String(120), nullable=False)
    event_type: Mapped[str] = mapped_column(String(40), nullable=False)
    amount_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(
        String(3), nullable=False, server_default=text("'INR'")
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    method: Mapped[str | None] = mapped_column(String(40))
    source: Mapped[str] = mapped_column(String(30), nullable=False)
    metadata_json: Mapped[dict | None] = mapped_column("metadata", JSONB)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("NOW()")
    )


class PaymentWebhookEvent(Base):
    __tablename__ = "payment_webhook_events"

    __table_args__ = (
        UniqueConstraint(
            "provider",
            "provider_event_id",
            name="uq_payment_webhook_events_provider_event_id",
        ),
        CheckConstraint(
            "processing_status IN ('received', 'processed', 'ignored_duplicate', 'ignored_out_of_order', 'rejected_signature', 'failed')",
            name="chk_payment_webhook_events_status",
        ),
        Index("idx_payment_webhook_events_org_id", "organisation_id"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger, Identity(always=True), primary_key=True
    )
    organisation_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("organisations.id")
    )
    provider_account_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("payment_provider_accounts.id")
    )
    provider: Mapped[str] = mapped_column(String(30), nullable=False)
    provider_event_id: Mapped[str] = mapped_column(String(120), nullable=False)
    event_type: Mapped[str] = mapped_column(String(80), nullable=False)
    provider_order_id: Mapped[str | None] = mapped_column(String(120))
    provider_payment_id: Mapped[str | None] = mapped_column(String(120))
    signature_valid: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("FALSE")
    )
    processing_status: Mapped[str] = mapped_column(
        String(30), nullable=False, server_default=text("'received'")
    )
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    sanitized_summary: Mapped[dict | None] = mapped_column(JSONB)
    error_message: Mapped[str | None] = mapped_column(Text)
    received_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("NOW()")
    )
    processed_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True)
    )
