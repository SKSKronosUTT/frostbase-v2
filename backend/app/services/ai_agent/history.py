"""Historial de una conversación: se lee del agente, no de FrostBase (B3)."""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.core.config import settings
from app.services.ai_agent.client import WebImClient
from app.services.ai_agent.conversations import (
    ConversationNotFoundError,
    get_conversation,
)
from app.services.ai_agent.text import sanitize_text
from app.utils.time import utcnow

ALLOWED_ROLES = {"user", "assistant", "system"}
PROMPT_PREFIX = "[Contexto FrostBase"
PROMPT_MARKER = "\n\nPregunta del administrador: "


def _seq(item: dict) -> int:
    try:
        return int(item.get("seq", 0))
    except (TypeError, ValueError):
        return 0


def _message_text(item: dict) -> str:
    """Quita el contexto push del mensaje del usuario para mostrarlo limpio."""
    text = str(item.get("text") or "")
    if (
        str(item.get("role")) == "user"
        and text.startswith(PROMPT_PREFIX)
        and PROMPT_MARKER in text
    ):
        return text.rsplit(PROMPT_MARKER, 1)[-1]
    return text


def read_messages(
    db: Session,
    *,
    admin_id: int,
    conversation_id: uuid.UUID,
    client: WebImClient,
    limit: int = 50,
) -> dict:
    """Devuelve los últimos ``limit`` mensajes de la sesión del agente.

    El backend no guarda el texto: si la sesión ya no existe en el ESP32 se
    responde 404. Cada mensaje se sanea y se recorta para acotar la respuesta.
    """
    conversation = get_conversation(
        db, admin_id=admin_id, conversation_id=conversation_id
    )
    if not conversation.agent_session:
        raise ConversationNotFoundError(
            "La conversación no tiene una sesión activa en el agente"
        )

    raw = client.messages(conversation.agent_session)
    ordered = sorted(raw, key=_seq)
    bounded = max(1, min(100, limit))
    selected = ordered[-bounded:]
    truncated = len(ordered) > len(selected)

    messages: list[dict] = []
    for item in selected:
        text, cut = sanitize_text(
            _message_text(item),
            limit=settings.ai_agent_max_reply_chars,
        )
        truncated = truncated or cut
        role = str(item.get("role") or "system")
        messages.append(
            {
                "seq": _seq(item),
                "role": role if role in ALLOWED_ROLES else "system",
                "text": text,
                "truncated": cut,
            }
        )

    return {
        "conversation_id": conversation.id,
        "generated_at": utcnow(),
        "total": len(ordered),
        "returned": len(messages),
        "truncated": truncated,
        "messages": messages,
    }
