"""Asistente IA: cuota diaria y conversaciones (G-IA / A1).

- ``ai_usage``: contador atómico por administrador y día; no guarda contenido.
- ``ai_conversations``: mapea el ``conversation_id`` del backend con la sesión
  del agente y el último ``seq`` visto. Tampoco guarda el texto del chat.
"""

import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Index, Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.utils.time import utcnow


class AiUsage(Base):
    __tablename__ = "ai_usage"
    __table_args__ = (
        Index(
            "uq_ai_usage_admin_day",
            "admin_id",
            "day",
            unique=True,
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    admin_id: Mapped[int] = mapped_column(
        ForeignKey("admins.id", ondelete="CASCADE"), nullable=False
    )
    day: Mapped[date] = mapped_column(Date, nullable=False)
    count: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", nullable=False
    )


class AiConversation(Base):
    __tablename__ = "ai_conversations"
    __table_args__ = (Index("ix_ai_conversations_admin", "admin_id", "last_used_at"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    admin_id: Mapped[int] = mapped_column(
        ForeignKey("admins.id", ondelete="CASCADE"), nullable=False
    )
    agent_session: Mapped[str | None] = mapped_column(String(100), nullable=True)
    last_seq: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    last_used_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    closed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    admin = relationship("Admin")


class AiAudit(Base):
    """Auditoría de uso del asistente: solo metadatos, nunca el texto del chat."""

    __tablename__ = "ai_audit"
    __table_args__ = (
        Index("ix_ai_audit_created", "created_at"),
        Index("ix_ai_audit_admin_created", "admin_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    admin_id: Mapped[int | None] = mapped_column(
        ForeignKey("admins.id", ondelete="SET NULL"), nullable=True
    )
    action: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    http_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    detail: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
