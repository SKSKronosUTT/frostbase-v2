"""Orquestación de una consulta al asistente (A1)."""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.admin import Admin
from app.services.ai_agent.client import (
    AgentDisabledError,
    AgentTimeoutError,
    AgentValidationError,
    WebImClient,
    build_client,
)
from app.services.ai_agent.context import build_context
from app.services.ai_agent.conversations import get_or_create
from app.services.ai_agent.gate import agent_lock
from app.services.ai_agent.quota import consume
from app.utils.time import utcnow


@dataclass
class ChatReply:
    conversation_id: uuid.UUID
    reply: str
    latency_ms: int


def _last_seq(messages: list[dict]) -> int:
    return max((int(message.get("seq", 0)) for message in messages), default=0)


def _wait_for_reply(
    client: WebImClient,
    session: str,
    baseline: int,
) -> dict:
    deadline = time.monotonic() + settings.ai_agent_timeout_seconds
    interval = max(0.2, settings.ai_agent_poll_interval_seconds)
    while time.monotonic() < deadline:
        time.sleep(min(interval, max(0.0, deadline - time.monotonic())))
        messages = client.messages(session)
        candidates = [
            message
            for message in messages
            if message.get("role") == "assistant"
            and int(message.get("seq", 0)) > baseline
        ]
        if candidates:
            return max(candidates, key=lambda item: int(item.get("seq", 0)))
    raise AgentTimeoutError(
        "El agente no devolvió una respuesta dentro del tiempo esperado"
    )


def chat(
    db: Session,
    admin: Admin,
    message: str,
    *,
    conversation_id: uuid.UUID | None = None,
    client: WebImClient | None = None,
) -> ChatReply:
    if not settings.ai_agent_enabled:
        raise AgentDisabledError("El asistente IA está deshabilitado")

    normalized = (message or "").strip()
    if not normalized:
        raise AgentValidationError("El mensaje no puede estar vacío")
    if len(normalized) > settings.ai_agent_max_message_chars:
        raise AgentValidationError(
            f"El mensaje supera {settings.ai_agent_max_message_chars} caracteres"
        )

    today = datetime.now(settings.tz).date()
    consume(
        db,
        admin_id=admin.id,
        day=today,
        limit=settings.ai_agent_daily_limit,
    )

    owns_client = client is None
    agent_client = client or build_client()
    try:
        with agent_lock():
            conversation = get_or_create(
                db,
                admin_id=admin.id,
                conversation_id=conversation_id,
                client=agent_client,
            )
            assert conversation.agent_session is not None
            session = conversation.agent_session

            baseline = _last_seq(agent_client.messages(session))
            context = build_context(db)
            prompt = f"{context}\n\nPregunta del administrador: {normalized}"
            started = time.perf_counter()
            agent_client.send_message(session, prompt, uuid.uuid4().hex)
            reply = _wait_for_reply(agent_client, session, baseline)
            latency_ms = int((time.perf_counter() - started) * 1000)

            conversation.last_seq = int(reply.get("seq", baseline))
            conversation.last_used_at = utcnow()
            db.add(conversation)
            db.flush()
    finally:
        if owns_client:
            agent_client.close()

    return ChatReply(
        conversation_id=conversation.id,
        reply=str(reply.get("text") or "").strip(),
        latency_ms=latency_ms,
    )
