"""Asistente IA para el administrador (A1–A5).

El backend es el único cliente del ESP32: aquí se aplican rol, CSRF, rate
limit, cuota diaria, lock distribuido y auditoría (sin contenido del chat).
"""

import time
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request, Response, status

from app.api.deps import CurrentAdmin, DbSession
from app.core.config import settings
from app.core.ratelimit import RateLimit
from app.schemas.ai import (
    AiChatIn,
    AiChatOut,
    AiConversationClosedOut,
    AiConversationMessagesOut,
    AiConversationOut,
    AiConversationRenameIn,
    AiMetricsOut,
    AiQuickItem,
    AiQuickOut,
    AiStatusOut,
    AiUsageOut,
)
from app.services import ai_agent
from app.services.ai_agent import audit, history, quota
from app.services.ai_agent.conversations import (
    ConversationTitleError,
    close_conversation,
    list_recent,
    rename_conversation,
)

router = APIRouter(prefix="/ai", tags=["Asistente IA"])

_chat_limiter = RateLimit(
    "ai:chat", limit=settings.ai_agent_rate_limit, window_seconds=60
)
_quick_limiter = RateLimit("ai:quick", limit=30, window_seconds=60)
_history_limiter = RateLimit("ai:history", limit=30, window_seconds=60)


def _audit(
    admin_id: int,
    action: str,
    http_status: int,
    *,
    latency_ms: int | None = None,
    conversation_id: UUID | None = None,
    detail: str | None = None,
) -> None:
    audit.record_event(
        admin_id=admin_id,
        action=action,
        status="ok" if http_status < 400 else "error",
        http_status=http_status,
        latency_ms=latency_ms,
        conversation_id=conversation_id,
        detail=detail,
    )


@router.post("/chat", response_model=AiChatOut)
def chat(
    payload: AiChatIn,
    request: Request,
    response: Response,
    admin: CurrentAdmin,
    db: DbSession,
) -> AiChatOut:
    _chat_limiter.check(request, response, extra=str(admin.id))
    try:
        result = ai_agent.chat(
            db,
            admin,
            payload.message,
            conversation_id=payload.conversation_id,
        )
    except (ai_agent.AgentDisabledError, ai_agent.ConversationNotFoundError) as exc:
        _audit(admin.id, "chat", 404, detail="disabled_or_not_found")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
    except ai_agent.AgentValidationError as exc:
        _audit(admin.id, "chat", 422, detail="validation")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc
    except ai_agent.QuotaExceededError as exc:
        _audit(admin.id, "chat", 429, detail="quota")
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=str(exc),
            headers={"Retry-After": "3600"},
        ) from exc
    except ai_agent.AgentBusyError as exc:
        _audit(admin.id, "chat", 429, detail="busy")
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=str(exc),
            headers={"Retry-After": "3"},
        ) from exc
    except ai_agent.AgentCircuitOpenError as exc:
        _audit(admin.id, "chat", 503, detail="breaker")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
            headers={"Retry-After": str(exc.retry_after)},
        ) from exc
    except ai_agent.AgentTimeoutError as exc:
        _audit(admin.id, "chat", 504, detail="timeout")
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT, detail=str(exc)
        ) from exc
    except (
        ai_agent.AgentProtocolError,
        ai_agent.AgentSessionNotFoundError,
    ) as exc:
        _audit(admin.id, "chat", 502, detail="protocol")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)
        ) from exc
    except (ai_agent.AgentUnavailableError, ai_agent.AgentConfigError) as exc:
        _audit(admin.id, "chat", 503, detail="unavailable")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc

    details = []
    if result.recovered:
        details.append("session_recovered")
    if result.truncated:
        details.append("reply_truncated")
    _audit(
        admin.id,
        "chat",
        200,
        latency_ms=result.latency_ms,
        conversation_id=result.conversation_id,
        detail=",".join(details) or None,
    )
    return AiChatOut(
        conversation_id=result.conversation_id,
        reply=result.reply,
        latency_ms=result.latency_ms,
    )


@router.get("/status", response_model=AiStatusOut)
def agent_status(_: CurrentAdmin, db: DbSession) -> AiStatusOut:
    payload = ai_agent.get_status()
    payload["last_agent_read_at"] = audit.last_read_at(db)
    return AiStatusOut(**payload)


@router.get("/usage", response_model=AiUsageOut)
def usage(admin: CurrentAdmin, db: DbSession) -> AiUsageOut:
    """Cuota diaria del administrador y hora de reinicio (medianoche local)."""
    today = datetime.now(settings.tz).date()
    data = quota.usage(
        db,
        admin_id=admin.id,
        day=today,
        limit=settings.ai_agent_daily_limit,
    )
    return AiUsageOut(**data)


@router.get("/metrics", response_model=AiMetricsOut)
def metrics(
    _: CurrentAdmin,
    db: DbSession,
    days: int = Query(default=7, ge=1, le=30),
) -> AiMetricsOut:
    """Uso agregado del asistente (sin contenido de conversaciones)."""
    return AiMetricsOut(**audit.metrics(db, days=days))


@router.get("/quick", response_model=list[AiQuickItem])
def quick_list(_: CurrentAdmin) -> list[AiQuickItem]:
    """Sugerencias rápidas disponibles (respuestas locales, sin LLM)."""
    return [AiQuickItem(**item) for item in ai_agent.list_quick()]


@router.post("/quick/{quick_id}", response_model=AiQuickOut)
def quick(
    quick_id: str,
    request: Request,
    response: Response,
    admin: CurrentAdmin,
    db: DbSession,
) -> AiQuickOut:
    _quick_limiter.check(request, response, extra=str(admin.id))
    started = time.perf_counter()
    try:
        title, text = ai_agent.quick_answer(db, quick_id)
    except ai_agent.UnknownQuickError as exc:
        _audit(admin.id, "quick", 404, detail=quick_id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
    _audit(
        admin.id,
        "quick",
        200,
        latency_ms=int((time.perf_counter() - started) * 1000),
        detail=quick_id,
    )
    return AiQuickOut(id=quick_id, title=title, text=text)


@router.get("/conversations", response_model=list[AiConversationOut])
def conversations(
    admin: CurrentAdmin,
    db: DbSession,
    limit: int = Query(default=20, ge=1, le=50),
) -> list[AiConversationOut]:
    """Conversaciones activas del administrador, de la más reciente a la antigua."""
    return [
        AiConversationOut.model_validate(conversation)
        for conversation in list_recent(db, admin_id=admin.id, limit=limit)
    ]


@router.get(
    "/conversations/{conversation_id}/messages",
    response_model=AiConversationMessagesOut,
)
def conversation_messages(
    conversation_id: UUID,
    request: Request,
    response: Response,
    admin: CurrentAdmin,
    db: DbSession,
    limit: int = Query(default=50, ge=1, le=100),
) -> AiConversationMessagesOut:
    """Historial leído del agente (el backend no guarda el texto)."""
    _history_limiter.check(request, response, extra=str(admin.id))
    started = time.perf_counter()
    try:
        with ai_agent.build_client() as client:
            data = history.read_messages(
                db,
                admin_id=admin.id,
                conversation_id=conversation_id,
                client=client,
                limit=limit,
            )
    except (ai_agent.AgentDisabledError, ai_agent.ConversationNotFoundError) as exc:
        _audit(admin.id, "messages", 404, conversation_id=conversation_id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
    except ai_agent.AgentSessionNotFoundError as exc:
        _audit(admin.id, "messages", 404, conversation_id=conversation_id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="La sesión del agente ya no está disponible",
        ) from exc
    except ai_agent.AgentProtocolError as exc:
        _audit(admin.id, "messages", 502, conversation_id=conversation_id)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)
        ) from exc
    except ai_agent.AgentTimeoutError as exc:
        _audit(admin.id, "messages", 504, conversation_id=conversation_id)
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT, detail=str(exc)
        ) from exc
    except (ai_agent.AgentUnavailableError, ai_agent.AgentConfigError) as exc:
        _audit(admin.id, "messages", 503, conversation_id=conversation_id)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc

    _audit(
        admin.id,
        "messages",
        200,
        latency_ms=int((time.perf_counter() - started) * 1000),
        conversation_id=conversation_id,
        detail="history",
    )
    return AiConversationMessagesOut(**data)


@router.patch("/conversations/{conversation_id}", response_model=AiConversationOut)
def rename(
    conversation_id: UUID,
    payload: AiConversationRenameIn,
    admin: CurrentAdmin,
    db: DbSession,
) -> AiConversationOut:
    """Renombra la conversación en el agente y guarda la etiqueta local."""
    try:
        with ai_agent.build_client() as client:
            conversation = rename_conversation(
                db,
                admin_id=admin.id,
                conversation_id=conversation_id,
                title=payload.title,
                client=client,
            )
    except ConversationTitleError as exc:
        _audit(admin.id, "rename", 422, conversation_id=conversation_id)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc
    except (ai_agent.AgentDisabledError, ai_agent.ConversationNotFoundError) as exc:
        _audit(admin.id, "rename", 404, conversation_id=conversation_id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
    except ai_agent.AgentSessionNotFoundError as exc:
        _audit(admin.id, "rename", 404, conversation_id=conversation_id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="La sesión del agente ya no está disponible",
        ) from exc
    except ai_agent.AgentProtocolError as exc:
        _audit(admin.id, "rename", 502, conversation_id=conversation_id)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)
        ) from exc
    except (ai_agent.AgentUnavailableError, ai_agent.AgentConfigError) as exc:
        _audit(admin.id, "rename", 503, conversation_id=conversation_id)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc

    _audit(
        admin.id,
        "rename",
        200,
        conversation_id=conversation_id,
        detail="renamed",
    )
    return AiConversationOut.model_validate(conversation)


@router.delete(
    "/conversations/{conversation_id}", response_model=AiConversationClosedOut
)
def close(
    conversation_id: UUID,
    admin: CurrentAdmin,
    db: DbSession,
) -> AiConversationClosedOut:
    try:
        with ai_agent.build_client() as client:
            conversation = close_conversation(
                db,
                admin_id=admin.id,
                conversation_id=conversation_id,
                client=client,
            )
    except (ai_agent.AgentDisabledError, ai_agent.ConversationNotFoundError) as exc:
        _audit(admin.id, "close", 404, conversation_id=conversation_id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
    except (ai_agent.AgentUnavailableError, ai_agent.AgentConfigError) as exc:
        _audit(admin.id, "close", 503, conversation_id=conversation_id)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc
    except ai_agent.AgentProtocolError as exc:
        _audit(admin.id, "close", 502, conversation_id=conversation_id)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)
        ) from exc

    _audit(admin.id, "close", 200, conversation_id=conversation.id)
    return AiConversationClosedOut(conversation_id=conversation.id)
