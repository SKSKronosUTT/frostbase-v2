"""Schemas del asistente IA (A1)."""

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


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
    last_agent_read_at: datetime | None = None


class AiUsageOut(BaseModel):
    limit: int
    used: int
    remaining: int
    day: date
    reset_at: datetime


class AiConversationClosedOut(BaseModel):
    conversation_id: UUID
    closed: bool = True


class AiConversationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str | None = None
    created_at: datetime
    last_used_at: datetime
    last_seq: int


class AiConversationRenameIn(BaseModel):
    title: str = Field(min_length=1, max_length=60)


class AiConversationMessageOut(BaseModel):
    seq: int
    role: str
    text: str
    truncated: bool = False


class AiConversationMessagesOut(BaseModel):
    conversation_id: UUID
    generated_at: datetime
    total: int
    returned: int
    truncated: bool = False
    messages: list[AiConversationMessageOut]


class AiQuickItem(BaseModel):
    id: str
    title: str


class AiQuickOut(BaseModel):
    id: str
    title: str
    text: str
    source: str = "system"


class AiMetricsOut(BaseModel):
    days: int
    generated_at: datetime
    requests: int
    errors: int
    by_action: dict[str, int]
    errors_by_http_status: dict[str, int]
    latency_avg_ms: float | None = None
    latency_p50_ms: int | None = None
    latency_p95_ms: int | None = None
