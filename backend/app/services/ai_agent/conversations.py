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


def get_or_create(
    db: Session,
    *,
    admin_id: int,
    conversation_id: uuid.UUID | None,
    client: WebImClient,
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
        conversation = AiConversation(admin_id=admin_id, last_seq=0)
        db.add(conversation)
        db.flush()

    # Política de memoria: si la sesión supera el TTL se rota (nueva sesión en
    # el agente) para no arrastrar contexto antiguo indefinidamente.
    if conversation.agent_session and _session_expired(conversation):
        client.delete_session(conversation.agent_session)
        conversation.agent_session = None
        conversation.last_seq = 0

    if not conversation.agent_session:
        conversation.agent_session = client.create_session()

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
