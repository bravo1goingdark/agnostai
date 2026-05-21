from datetime import datetime
from typing import Any
from uuid import UUID as PyUUID
from uuid import uuid4

from pgvector.sqlalchemy import Vector  # type: ignore[import-untyped]
from sqlalchemy import (
    JSON,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base

json_column = JSON().with_variant(JSONB, "postgresql")


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    api_key_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        json_column,
        default=dict,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Conversation(Base):
    __tablename__ = "conversations"
    __table_args__ = (
        UniqueConstraint(
            "project_id",
            "external_id",
            name="uq_conversations_project_external_id",
        ),
        UniqueConstraint(
            "project_id",
            "content_hash",
            name="uq_conversations_project_content_hash",
        ),
        Index("ix_conversations_project_created_at", "project_id", "created_at"),
    )

    id: Mapped[PyUUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="RESTRICT"),
        index=True,
        nullable=False,
    )
    external_id: Mapped[str] = mapped_column(String(256), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    raw_payload: Mapped[dict[str, Any]] = mapped_column(json_column, nullable=False)
    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        json_column,
        default=dict,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (
        UniqueConstraint(
            "conversation_id",
            "sequence_index",
            name="uq_messages_conversation_sequence",
        ),
        Index("ix_messages_project_created_at", "project_id", "created_at"),
        Index("ix_messages_project_role", "project_id", "role"),
        Index("ix_messages_project_text_hash", "project_id", "normalized_text_hash"),
    )

    id: Mapped[PyUUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="RESTRICT"),
        nullable=False,
    )
    conversation_id: Mapped[PyUUID] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
    )
    external_id: Mapped[str | None] = mapped_column(String(256), nullable=True)
    sequence_index: Mapped[int] = mapped_column(Integer, nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_text_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    sentiment_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    sentiment_label: Mapped[str | None] = mapped_column(String(32), nullable=True)
    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        json_column,
        default=dict,
        nullable=False,
    )
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class MessageEmbedding(Base):
    __tablename__ = "message_embeddings"
    __table_args__ = (
        UniqueConstraint(
            "message_id",
            "model_name",
            name="uq_message_embeddings_message_model",
        ),
        Index("ix_message_embeddings_project_model", "project_id", "model_name"),
    )

    id: Mapped[PyUUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="RESTRICT"),
        nullable=False,
    )
    message_id: Mapped[PyUUID] = mapped_column(
        ForeignKey("messages.id", ondelete="CASCADE"),
        nullable=False,
    )
    model_name: Mapped[str] = mapped_column(String(255), nullable=False)
    dimension: Mapped[int] = mapped_column(Integer, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector(384), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ClusterRun(Base):
    __tablename__ = "cluster_runs"
    __table_args__ = (
        Index("ix_cluster_runs_project_created_at", "project_id", "created_at"),
        Index("ix_cluster_runs_project_window", "project_id", "window_start"),
    )

    id: Mapped[PyUUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="RESTRICT"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="queued")
    window_start: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    window_end: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    parameters: Mapped[dict[str, Any]] = mapped_column(
        json_column,
        default=dict,
        nullable=False,
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )


class Topic(Base):
    __tablename__ = "topics"
    __table_args__ = (
        UniqueConstraint(
            "cluster_run_id",
            "cluster_label",
            name="uq_topics_cluster_run_label",
        ),
        Index("ix_topics_project_created_at", "project_id", "created_at"),
        Index("ix_topics_project_label", "project_id", "label"),
    )

    id: Mapped[PyUUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="RESTRICT"),
        nullable=False,
    )
    cluster_run_id: Mapped[PyUUID] = mapped_column(
        ForeignKey("cluster_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    cluster_label: Mapped[int] = mapped_column(Integer, nullable=False)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    terms: Mapped[list[str]] = mapped_column(json_column, default=list, nullable=False)
    member_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    growth_24h: Mapped[float | None] = mapped_column(Float, nullable=True)
    growth_7d: Mapped[float | None] = mapped_column(Float, nullable=True)
    sentiment_mean: Mapped[float | None] = mapped_column(Float, nullable=True)
    negative_sentiment_share: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )
    first_seen_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    last_seen_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class TopicMembership(Base):
    __tablename__ = "topic_memberships"
    __table_args__ = (
        UniqueConstraint(
            "topic_id",
            "message_id",
            name="uq_topic_memberships_topic_message",
        ),
        Index("ix_topic_memberships_project_topic", "project_id", "topic_id"),
        Index("ix_topic_memberships_message", "message_id"),
    )

    id: Mapped[PyUUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="RESTRICT"),
        nullable=False,
    )
    topic_id: Mapped[PyUUID] = mapped_column(
        ForeignKey("topics.id", ondelete="CASCADE"),
        nullable=False,
    )
    message_id: Mapped[PyUUID] = mapped_column(
        ForeignKey("messages.id", ondelete="CASCADE"),
        nullable=False,
    )
    similarity: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_representative: Mapped[bool] = mapped_column(nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ProcessingJob(Base):
    __tablename__ = "processing_jobs"
    __table_args__ = (
        Index("ix_processing_jobs_project_status", "project_id", "status"),
        Index("ix_processing_jobs_created_at", "created_at"),
    )

    id: Mapped[PyUUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid4,
    )
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="RESTRICT"),
        index=True,
        nullable=False,
    )
    conversation_id: Mapped[PyUUID] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    job_type: Mapped[str] = mapped_column(String(64), nullable=False)
    arq_job_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="queued")
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    enqueued_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
