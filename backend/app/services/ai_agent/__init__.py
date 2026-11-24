"""Servicio del asistente IA sobre ESP-Claw (A1)."""

from app.services.ai_agent.chat import ChatReply, chat
from app.services.ai_agent.client import (
    AgentBusyError,
    AgentCircuitOpenError,
    AgentConfigError,
    AgentDisabledError,
    AgentProtocolError,
    AgentSessionNotFoundError,
    AgentTimeoutError,
    AgentUnavailableError,
    AgentValidationError,
    build_client,
)
from app.services.ai_agent.conversations import (
    ConversationNotFoundError,
    close_conversation,
)
from app.services.ai_agent.quick import (
    UnknownQuickError,
    list_quick,
    quick_answer,
)
from app.services.ai_agent.quota import QuotaExceededError
from app.services.ai_agent.status import get_status, reset_status_cache

__all__ = [
    "AgentBusyError",
    "AgentCircuitOpenError",
    "AgentConfigError",
    "AgentDisabledError",
    "AgentProtocolError",
    "AgentSessionNotFoundError",
    "AgentTimeoutError",
    "AgentUnavailableError",
    "AgentValidationError",
    "ChatReply",
    "ConversationNotFoundError",
    "QuotaExceededError",
    "UnknownQuickError",
    "build_client",
    "chat",
    "close_conversation",
    "get_status",
    "list_quick",
    "quick_answer",
    "reset_status_cache",
]
