"""Asistente IA para el administrador (A1).

El backend es el único cliente del ESP32: aquí se aplican rol, CSRF, rate
limit, cuota diaria y el lock distribuido antes de llamar al agente.
"""

from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, Response, status

from app.api.deps import CurrentAdmin, DbSession
from app.core.config import settings
from app.core.ratelimit import RateLimit
from app.schemas.ai import (
    AiChatIn,
    AiChatOut,
    AiConversationClosedOut,
    AiStatusOut,
)
from app.services import ai_agent
from app.services.ai_agent.conversations import close_conversation

router = APIRouter(prefix="/ai", tags=["Asistente IA"])

_chat_limiter = RateLimit(
    "ai:chat", limit=settings.ai_agent_rate_limit, window_seconds=60
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
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
    except ai_agent.AgentValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc
    except ai_agent.QuotaExceededError as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=str(exc),
            headers={"Retry-After": "3600"},
        ) from exc
    except ai_agent.AgentBusyError as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=str(exc),
            headers={"Retry-After": "3"},
        ) from exc
    except ai_agent.AgentTimeoutError as exc:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT, detail=str(exc)
        ) from exc
    except ai_agent.AgentProtocolError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)
        ) from exc
    except (ai_agent.AgentUnavailableError, ai_agent.AgentConfigError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc

    return AiChatOut(
        conversation_id=result.conversation_id,
        reply=result.reply,
        latency_ms=result.latency_ms,
    )


@router.get("/status", response_model=AiStatusOut)
def agent_status(_: CurrentAdmin) -> AiStatusOut:
    return AiStatusOut(**ai_agent.get_status())


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
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
    except (ai_agent.AgentUnavailableError, ai_agent.AgentConfigError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc
    except ai_agent.AgentProtocolError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)
        ) from exc

    return AiConversationClosedOut(conversation_id=conversation.id)
