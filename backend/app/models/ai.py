"""Asistente IA: cuota diaria y conversaciones (G-IA / A1).

- ``ai_usage``: contador atómico por administrador y día; no guarda contenido.
- ``ai_conversations``: mapea el ``conversation_id`` del backend con la sesión
  del agente, su ``boot_id`` y el último ``seq`` visto. Tampoco guarda el texto.
- ``ai_breaker``: estado del cortacircuito del agente (una fila compartida).
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
    # Etiqueta local editable por el administrador; nunca se deriva del chat.
    title: Mapped[str | None] = mapped_column(String(60), nullable=True)
    # ``boot_id`` del ESP32 con el que se creó la sesión: si cambia (reinicio),
    # la sesión deja de ser válida y se rota antes de usarla.
    agent_boot_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
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


class AiBreaker(Base):
    """Estado del cortacircuito del agente, compartido entre workers.

    Una sola fila (``id=1``): tras ``AI_AGENT_BREAKER_FAILURES`` fallos
    consecutivos se guarda ``opened_until`` y se responde 503 sin llamar al
    ESP32 hasta que expire.
    """

    __tablename__ = "ai_breaker"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    failures: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", nullable=False
    )
    opened_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )


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
