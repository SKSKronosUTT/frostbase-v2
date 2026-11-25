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
    ConversationTitleError,
    close_conversation,
    list_recent,
    rename_conversation,
)
from app.services.ai_agent.quick import (
    QuickTruckNotFoundError,
    QuickTruckRequiredError,
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
    "ConversationTitleError",
    "QuickTruckNotFoundError",
    "QuickTruckRequiredError",
    "QuotaExceededError",
    "UnknownQuickError",
    "build_client",
    "chat",
    "close_conversation",
    "get_status",
    "list_quick",
    "list_recent",
    "quick_answer",
    "rename_conversation",
    "reset_status_cache",
]
