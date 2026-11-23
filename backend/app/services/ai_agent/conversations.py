"""Conversaciones del asistente: UUID propio ↔ sesión del agente."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.ai import AiConversation
from app.services.ai_agent.client import WebImClient
from app.utils.time import utcnow


class ConversationNotFoundError(Exception):
    pass


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
