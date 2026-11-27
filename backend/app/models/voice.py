from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    ForeignKey,
    Identity,
    Index,
    Integer,
    String,
    Text,
    TIMESTAMP,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class VoiceSession(Base):
    __tablename__ = "voice_sessions"

    __table_args__ = (
        CheckConstraint(
            "language_mode IN ('en', 'hi', 'hinglish', 'auto')",
            name="chk_voice_sessions_language",
        ),
        Index("idx_voice_sessions_org_user", "organisation_id", "user_id"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger, Identity(always=True), primary_key=True
    )
    organisation_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("organisations.id"), nullable=False
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id"), nullable=False
    )
    language_mode: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'auto'")
    )
    title: Mapped[str] = mapped_column(
        String(200), nullable=False, server_default=text("'FLASHCORE Voice Session'")
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("NOW()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("NOW()")
    )


class VoiceMessage(Base):
    __tablename__ = "voice_messages"

    __table_args__ = (
        CheckConstraint(
            "role IN ('user', 'assistant', 'tool')",
            name="chk_voice_messages_role",
        ),
        Index("idx_voice_messages_org_id", "organisation_id"),
        Index("idx_voice_messages_session_id", "session_id"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger, Identity(always=True), primary_key=True
    )
    organisation_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("organisations.id"), nullable=False
    )
    session_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("voice_sessions.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    transcript_language: Mapped[str | None] = mapped_column(String(20))
    stt_provider: Mapped[str | None] = mapped_column(String(60))
    tts_provider: Mapped[str | None] = mapped_column(String(60))
    tool_calls: Mapped[dict | list | None] = mapped_column(JSONB)
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("NOW()")
    )


class AiActionProposal(Base):
    __tablename__ = "ai_action_proposals"

    __table_args__ = (
        CheckConstraint(
            "status IN ('PENDING_APPROVAL', 'APPROVED', 'REJECTED', 'EXECUTED', 'FAILED')",
            name="chk_ai_action_proposals_status",
        ),
        Index("idx_ai_action_proposals_org_id", "organisation_id"),
        Index("idx_ai_action_proposals_session_id", "session_id"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger, Identity(always=True), primary_key=True
    )
    organisation_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("organisations.id"), nullable=False
    )
    session_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("voice_sessions.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id"), nullable=False
    )
    tool_name: Mapped[str] = mapped_column(String(80), nullable=False)
    arguments_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, server_default=text("'PENDING_APPROVAL'")
    )
    approved_by: Mapped[str | None] = mapped_column(String(150))
    approved_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    executed_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    result_json: Mapped[dict | None] = mapped_column(JSONB)
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("NOW()")
    )


class AiUsageLog(Base):
    __tablename__ = "ai_usage_logs"

    __table_args__ = (
        CheckConstraint(
            "status IN ('success', 'error', 'blocked')",
            name="chk_ai_usage_logs_status",
        ),
        Index("idx_ai_usage_logs_org_id", "organisation_id"),
        Index("idx_ai_usage_logs_created_at", "created_at"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger, Identity(always=True), primary_key=True
    )
    organisation_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("organisations.id"), nullable=False
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id"), nullable=False
    )
    provider: Mapped[str] = mapped_column(String(40), nullable=False)
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    operation: Mapped[str] = mapped_column(String(40), nullable=False)
    prompt_tokens: Mapped[int | None] = mapped_column(Integer)
    completion_tokens: Mapped[int | None] = mapped_column(Integer)
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    error_detail: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("NOW()")
    )
