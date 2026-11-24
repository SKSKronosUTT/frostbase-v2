"""Conversaciones del asistente: UUID propio ↔ sesión del agente."""

from __future__ import annotations

import uuid
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.ai import AiConversation
from app.services.ai_agent.client import WebImClient
from app.utils.time import ensure_utc, utcnow


class ConversationNotFoundError(Exception):
    pass


def _session_expired(conversation: AiConversation) -> bool:
    ttl_hours = settings.ai_agent_session_ttl_hours
    if ttl_hours <= 0:
        return False
    last_used = ensure_utc(conversation.last_used_at) or utcnow()
    return (utcnow() - last_used) > timedelta(hours=ttl_hours)


def _rotate_session(
    conversation: AiConversation,
    client: WebImClient,
    *,
    boot_id: str | None,
) -> None:
    """Crea una sesión nueva y descarta la anterior (best-effort)."""
    if conversation.agent_session:
        client.delete_session(conversation.agent_session)
    conversation.agent_session = client.create_session()
    conversation.agent_boot_id = boot_id
    conversation.last_seq = 0


def rotate_session(
    db: Session,
    conversation: AiConversation,
    client: WebImClient,
    *,
    boot_id: str | None = None,
) -> AiConversation:
    """Rota la sesión del agente, p. ej. si desapareció o el ESP32 reinició."""
    _rotate_session(conversation, client, boot_id=boot_id)
    conversation.last_used_at = utcnow()
    db.add(conversation)
    db.flush()
    return conversation


def _close_excess(
    db: Session,
    *,
    admin_id: int,
    client: WebImClient,
) -> None:
    """Cierra las conversaciones activas más antiguas al superar el máximo."""
    limit = settings.ai_agent_max_conversations
    if limit <= 0:
        return
    active = list(
        db.scalars(
            select(AiConversation)
            .where(
                AiConversation.admin_id == admin_id,
                AiConversation.closed_at.is_(None),
            )
            .order_by(AiConversation.last_used_at)
        )
    )
    excess = len(active) - limit + 1
    for conversation in active[: max(0, excess)]:
        if conversation.agent_session:
            client.delete_session(conversation.agent_session)
        conversation.closed_at = utcnow()
        db.add(conversation)
    if excess > 0:
        db.flush()


def get_or_create(
    db: Session,
    *,
    admin_id: int,
    conversation_id: uuid.UUID | None,
    client: WebImClient,
    boot_id: str | None = None,
) -> AiConversation:
    conversation: AiConversation | None = None
    if conversation_id is not None:
        conversation = db.scalar(
            select(AiConversation).where(
                AiConversation.id == conversation_id,
                AiConversation.admin_id == admin_id,
                AiConversation.closed_at.is_(None),
            )
        )
        if conversation is None:
            raise ConversationNotFoundError("Conversación no encontrada")

    if conversation is None:
        _close_excess(db, admin_id=admin_id, client=client)
        conversation = AiConversation(admin_id=admin_id, last_seq=0)
        db.add(conversation)
        db.flush()

    # Política de memoria: si la sesión supera el TTL se rota (nueva sesión en
    # el agente) para no arrastrar contexto antiguo indefinidamente. Si el
    # ESP32 reinició (``boot_id`` distinto), la sesión ya no existe: se rota
    # antes de intentar usarla.
    boot_changed = bool(
        conversation.agent_session
        and conversation.agent_boot_id
        and boot_id
        and conversation.agent_boot_id != boot_id
    )
    if conversation.agent_session and (boot_changed or _session_expired(conversation)):
        _rotate_session(conversation, client, boot_id=boot_id)
    elif not conversation.agent_session:
        conversation.agent_session = client.create_session()
        conversation.agent_boot_id = boot_id

    if boot_id and conversation.agent_boot_id is None:
        conversation.agent_boot_id = boot_id

    conversation.last_used_at = utcnow()
    db.add(conversation)
    db.flush()
    return conversation


def close_conversation(
    db: Session,
    *,
    admin_id: int,
    conversation_id: uuid.UUID,
    client: WebImClient,
) -> AiConversation:
    conversation = db.scalar(
        select(AiConversation).where(
            AiConversation.id == conversation_id,
            AiConversation.admin_id == admin_id,
            AiConversation.closed_at.is_(None),
        )
    )
    if conversation is None:
        raise ConversationNotFoundError("Conversación no encontrada")
    if conversation.agent_session:
        client.delete_session(conversation.agent_session)
    conversation.closed_at = utcnow()
    conversation.last_used_at = utcnow()
    db.add(conversation)
    db.flush()
    return conversation
