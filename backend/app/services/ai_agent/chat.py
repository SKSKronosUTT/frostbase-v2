"""Orquestación de una consulta al asistente (A1 + B1)."""

from __future__ import annotations

import re
import time
import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.admin import Admin
from app.models.ai import AiConversation
from app.services.ai_agent import breaker
from app.services.ai_agent.client import (
    AgentDisabledError,
    AgentProtocolError,
    AgentSessionNotFoundError,
    AgentTimeoutError,
    AgentUnavailableError,
    AgentValidationError,
    WebImClient,
    build_client,
)
from app.services.ai_agent.context import build_context
from app.services.ai_agent.conversations import get_or_create, rotate_session
from app.services.ai_agent.gate import agent_lock
from app.services.ai_agent.quota import consume
from app.utils.time import utcnow

_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

# Fallos que abren el cortacircuito (todo lo que implique que el agente no
# respondió correctamente; la validación del mensaje nunca cuenta).
_BREAKER_ERRORS = (
    AgentUnavailableError,
    AgentTimeoutError,
    AgentProtocolError,
    AgentSessionNotFoundError,
)


@dataclass
class ChatReply:
    conversation_id: uuid.UUID
    reply: str
    latency_ms: int
    recovered: bool = False
    truncated: bool = False


def _last_seq(messages: list[dict]) -> int:
    return max((int(message.get("seq", 0)) for message in messages), default=0)


def _prepare_reply(text: str) -> tuple[str, bool]:
    """Quita caracteres de control y limita el tamaño de la respuesta."""
    cleaned = _CONTROL_CHARS.sub("", text).strip()
    limit = max(1, settings.ai_agent_max_reply_chars)
    return cleaned[:limit], len(cleaned) > limit


def _probe_boot_id(client: WebImClient) -> str | None:
    """Lee el ``boot_id`` del ESP32 para detectar reinicios. Best-effort."""
    timeout = settings.ai_agent_boot_probe_seconds
    if timeout <= 0:
        return None
    return client.status(timeout=timeout).boot_id


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


def _exchange(
    db: Session,
    conversation: AiConversation,
    client: WebImClient,
    prompt: str,
    *,
    boot_id: str | None,
) -> tuple[dict, bool]:
    """Envía el mensaje y espera la respuesta, recuperando la sesión una vez."""
    session = conversation.agent_session
    assert session is not None
    for attempt in range(2):
        try:
            baseline = _last_seq(client.messages(session))
            client.send_message(session, prompt, uuid.uuid4().hex)
            return _wait_for_reply(client, session, baseline), attempt > 0
        except AgentSessionNotFoundError:
            if attempt > 0:
                raise
            conversation = rotate_session(db, conversation, client, boot_id=boot_id)
            session = conversation.agent_session
            assert session is not None
    raise AgentProtocolError("No se pudo recuperar la conversación del agente")


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

    # Si el agente está caído, no se descuenta cuota ni se espera el lock.
    breaker.ensure_closed()

    today = datetime.now(settings.tz).date()
    owns_client = client is None
    agent_client = client or build_client()
    conversation: AiConversation | None = None
    try:
        with agent_lock():
            consume(
                db,
                admin_id=admin.id,
                day=today,
                limit=settings.ai_agent_daily_limit,
            )
            try:
                boot_id = _probe_boot_id(agent_client)
                conversation = get_or_create(
                    db,
                    admin_id=admin.id,
                    conversation_id=conversation_id,
                    client=agent_client,
                    boot_id=boot_id,
                )
                context = build_context(db)
                prompt = f"{context}\n\nPregunta del administrador: {normalized}"
                started = time.perf_counter()
                reply, recovered = _exchange(
                    db,
                    conversation,
                    agent_client,
                    prompt,
                    boot_id=boot_id,
                )
            except _BREAKER_ERRORS:
                breaker.record_failure()
                raise
            latency_ms = int((time.perf_counter() - started) * 1000)
            breaker.record_success()

            conversation.last_seq = int(reply.get("seq", conversation.last_seq))
            conversation.last_used_at = utcnow()
            db.add(conversation)
            db.flush()
    finally:
        if owns_client:
            agent_client.close()

    assert conversation is not None
    reply_text, truncated = _prepare_reply(str(reply.get("text") or ""))
    return ChatReply(
        conversation_id=conversation.id,
        reply=reply_text,
        latency_ms=latency_ms,
        recovered=recovered,
        truncated=truncated,
    )
