from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

MessageRole = Literal["user", "assistant", "system", "tool"]


class ConversationMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

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


class TopicMessageExample(BaseModel):
    message_id: str
    conversation_id: str
    role: MessageRole
    content: str
    similarity: float | None = None
    sentiment_score: float | None = None
    sentiment_label: str | None = None
    created_at: datetime | None = None


class TopicSummary(BaseModel):
    id: str
    cluster_run_id: str
    cluster_label: int
    label: str
    summary: str | None = None
    terms: list[str] = Field(default_factory=list)
    member_count: int
    growth_24h: float | None = None
    growth_7d: float | None = None
    sentiment_mean: float | None = None
    negative_sentiment_share: float | None = None
    first_seen_at: datetime | None = None
    last_seen_at: datetime | None = None
    representative_examples: list[str] = Field(default_factory=list)


class TopicDetailResponse(TopicSummary):
    project_id: str
    source_conversation_ids: list[str] = Field(default_factory=list)
    messages: list[TopicMessageExample] = Field(default_factory=list)
    prior_cluster_runs: list[str] = Field(default_factory=list)


class TopicListResponse(BaseModel):
    project_id: str
    latest_cluster_run_id: str | None = None
    topics: list[TopicSummary] = Field(default_factory=list)


class InsightsResponse(BaseModel):
    project_id: str
    latest_cluster_run_id: str | None = None
    generated_at: datetime
    total_messages: int
    total_topics: int
    top_topics: list[TopicSummary] = Field(default_factory=list)
    sentiment_distribution: dict[str, float | int] = Field(default_factory=dict)
    emerging_topics: list[TopicSummary] = Field(default_factory=list)


class ReportResponse(BaseModel):
    project_id: str
    latest_cluster_run_id: str | None = None
    report_text: str


class DemoBootstrapRequest(BaseModel):
    project_id: str = Field(min_length=1, max_length=128)


class DemoBootstrapResponse(BaseModel):
    project_id: str
    accepted: int
    duplicate: int
    processed: int
    topic_count: int
    latest_cluster_run_id: str | None = None
    report_path: str
    report_text: str
    insights: InsightsResponse
    topics: list[TopicSummary] = Field(default_factory=list)
