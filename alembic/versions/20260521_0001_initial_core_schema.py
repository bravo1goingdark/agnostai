"""Create core conversation intelligence schema.

Revision ID: 20260521_0001
Revises:
Create Date: 2026-05-21

"""
from collections.abc import Sequence

import pgvector.sqlalchemy
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260521_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "projects",
        sa.Column("id", sa.String(length=128), nullable=False),
        sa.Column("api_key_hash", sa.String(length=255), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_projects")),
    )

    op.create_table(
        "conversations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.String(length=128), nullable=False),
        sa.Column("external_id", sa.String(length=256), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "raw_payload",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name=op.f("fk_conversations_project_id_projects"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_conversations")),
        sa.UniqueConstraint(
            "project_id",
            "content_hash",
            name="uq_conversations_project_content_hash",
        ),
        sa.UniqueConstraint(
            "project_id",
            "external_id",
            name="uq_conversations_project_external_id",
        ),
    )
    op.create_index(
        op.f("ix_conversations_project_id"),
        "conversations",
        ["project_id"],
        unique=False,
    )
    op.create_index(
        "ix_conversations_project_created_at",
        "conversations",
        ["project_id", "created_at"],
        unique=False,
    )

    op.create_table(
        "cluster_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("window_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "parameters",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name=op.f("fk_cluster_runs_project_id_projects"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_cluster_runs")),
    )
    op.create_index(
        "ix_cluster_runs_project_created_at",
        "cluster_runs",
        ["project_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_cluster_runs_project_window",
        "cluster_runs",
        ["project_id", "window_start"],
        unique=False,
    )

    op.create_table(
        "messages",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.String(length=128), nullable=False),
        sa.Column("conversation_id", sa.Uuid(), nullable=False),
        sa.Column("external_id", sa.String(length=256), nullable=True),
        sa.Column("sequence_index", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("normalized_text_hash", sa.String(length=64), nullable=False),
        sa.Column("sentiment_score", sa.Float(), nullable=True),
        sa.Column("sentiment_label", sa.String(length=32), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "ingested_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["conversation_id"],
            ["conversations.id"],
            name=op.f("fk_messages_conversation_id_conversations"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name=op.f("fk_messages_project_id_projects"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_messages")),
        sa.UniqueConstraint(
            "conversation_id",
            "sequence_index",
            name="uq_messages_conversation_sequence",
        ),
    )
    op.create_index(
        "ix_messages_project_created_at",
        "messages",
        ["project_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_messages_project_role",
        "messages",
        ["project_id", "role"],
        unique=False,
    )
    op.create_index(
        "ix_messages_project_text_hash",
        "messages",
        ["project_id", "normalized_text_hash"],
        unique=False,
    )

    op.create_table(
        "processing_jobs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.String(length=128), nullable=False),
        sa.Column("conversation_id", sa.Uuid(), nullable=False),
        sa.Column("job_type", sa.String(length=64), nullable=False),
        sa.Column("arq_job_id", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column(
            "enqueued_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["conversation_id"],
            ["conversations.id"],
            name=op.f("fk_processing_jobs_conversation_id_conversations"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name=op.f("fk_processing_jobs_project_id_projects"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_processing_jobs")),
    )
    op.create_index(
        op.f("ix_processing_jobs_conversation_id"),
        "processing_jobs",
        ["conversation_id"],
        unique=False,
    )
    op.create_index(
        "ix_processing_jobs_created_at",
        "processing_jobs",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_processing_jobs_project_id"),
        "processing_jobs",
        ["project_id"],
        unique=False,
    )
    op.create_index(
        "ix_processing_jobs_project_status",
        "processing_jobs",
        ["project_id", "status"],
        unique=False,
    )

    op.create_table(
        "message_embeddings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.String(length=128), nullable=False),
        sa.Column("message_id", sa.Uuid(), nullable=False),
        sa.Column("model_name", sa.String(length=255), nullable=False),
        sa.Column("dimension", sa.Integer(), nullable=False),
        sa.Column("embedding", pgvector.sqlalchemy.Vector(dim=384), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["message_id"],
            ["messages.id"],
            name=op.f("fk_message_embeddings_message_id_messages"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name=op.f("fk_message_embeddings_project_id_projects"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_message_embeddings")),
        sa.UniqueConstraint(
            "message_id",
            "model_name",
            name="uq_message_embeddings_message_model",
        ),
    )
    op.create_index(
        "ix_message_embeddings_project_model",
        "message_embeddings",
        ["project_id", "model_name"],
        unique=False,
    )

    op.create_table(
        "topics",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.String(length=128), nullable=False),
        sa.Column("cluster_run_id", sa.Uuid(), nullable=False),
        sa.Column("cluster_label", sa.Integer(), nullable=False),
        sa.Column("label", sa.String(length=255), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("terms", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("member_count", sa.Integer(), nullable=False),
        sa.Column("growth_24h", sa.Float(), nullable=True),
        sa.Column("growth_7d", sa.Float(), nullable=True),
        sa.Column("sentiment_mean", sa.Float(), nullable=True),
        sa.Column("negative_sentiment_share", sa.Float(), nullable=True),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["cluster_run_id"],
            ["cluster_runs.id"],
            name=op.f("fk_topics_cluster_run_id_cluster_runs"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name=op.f("fk_topics_project_id_projects"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_topics")),
        sa.UniqueConstraint(
            "cluster_run_id",
            "cluster_label",
            name="uq_topics_cluster_run_label",
        ),
    )
    op.create_index(
        "ix_topics_project_created_at",
        "topics",
        ["project_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_topics_project_label",
        "topics",
        ["project_id", "label"],
        unique=False,
    )

    op.create_table(
        "topic_memberships",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.String(length=128), nullable=False),
        sa.Column("topic_id", sa.Uuid(), nullable=False),
        sa.Column("message_id", sa.Uuid(), nullable=False),
        sa.Column("similarity", sa.Float(), nullable=True),
        sa.Column("is_representative", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["message_id"],
            ["messages.id"],
            name=op.f("fk_topic_memberships_message_id_messages"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name=op.f("fk_topic_memberships_project_id_projects"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["topic_id"],
            ["topics.id"],
            name=op.f("fk_topic_memberships_topic_id_topics"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_topic_memberships")),
        sa.UniqueConstraint(
            "topic_id",
            "message_id",
            name="uq_topic_memberships_topic_message",
        ),
    )
    op.create_index(
        "ix_topic_memberships_message",
        "topic_memberships",
        ["message_id"],
        unique=False,
    )
    op.create_index(
        "ix_topic_memberships_project_topic",
        "topic_memberships",
        ["project_id", "topic_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_topic_memberships_project_topic", table_name="topic_memberships")
    op.drop_index("ix_topic_memberships_message", table_name="topic_memberships")
    op.drop_table("topic_memberships")
    op.drop_index("ix_topics_project_label", table_name="topics")
    op.drop_index("ix_topics_project_created_at", table_name="topics")
    op.drop_table("topics")
    op.drop_index(
        "ix_message_embeddings_project_model",
        table_name="message_embeddings",
    )
    op.drop_table("message_embeddings")
    op.drop_index("ix_processing_jobs_project_status", table_name="processing_jobs")
    op.drop_index(op.f("ix_processing_jobs_project_id"), table_name="processing_jobs")
    op.drop_index("ix_processing_jobs_created_at", table_name="processing_jobs")
    op.drop_index(
        op.f("ix_processing_jobs_conversation_id"),
        table_name="processing_jobs",
    )
    op.drop_table("processing_jobs")
    op.drop_index("ix_messages_project_text_hash", table_name="messages")
    op.drop_index("ix_messages_project_role", table_name="messages")
    op.drop_index("ix_messages_project_created_at", table_name="messages")
    op.drop_table("messages")
    op.drop_index("ix_cluster_runs_project_window", table_name="cluster_runs")
    op.drop_index("ix_cluster_runs_project_created_at", table_name="cluster_runs")
    op.drop_table("cluster_runs")
    op.drop_index("ix_conversations_project_created_at", table_name="conversations")
    op.drop_index(op.f("ix_conversations_project_id"), table_name="conversations")
    op.drop_table("conversations")
    op.drop_table("projects")
    op.execute("DROP EXTENSION IF EXISTS vector")
