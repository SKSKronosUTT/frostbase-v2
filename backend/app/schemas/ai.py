"""Schemas del asistente IA (A1)."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class AiChatIn(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    conversation_id: UUID | None = None


class AiChatOut(BaseModel):
    conversation_id: UUID
    reply: str
    source: str = "agent"
    latency_ms: int


class AiStatusOut(BaseModel):
    enabled: bool
    online: bool
    latency_ms: float | None = None
    boot_id: str | None = None
    wifi_connected: bool | None = None
    last_ok_at: datetime | None = None


class AiConversationClosedOut(BaseModel):
    conversation_id: UUID
    closed: bool = True
