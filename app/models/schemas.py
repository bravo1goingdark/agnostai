from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

MessageRole = Literal["user", "assistant", "system", "tool"]


class ConversationMessage(BaseModel):
    model_config = ConfigDict(extra="allow")

    message_id: str | None = None
    role: MessageRole
    content: str = Field(min_length=1, max_length=50_000)
    created_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ConversationIngestRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_id: str = Field(min_length=1, max_length=128)
    conversation_id: str = Field(min_length=1, max_length=256)
    messages: list[ConversationMessage] = Field(min_length=1, max_length=500)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ConversationIngestResponse(BaseModel):
    project_id: str
    conversation_id: str
    status: Literal["accepted", "duplicate"]
    job_id: str | None = None
    stored_conversation_id: str | None = None
