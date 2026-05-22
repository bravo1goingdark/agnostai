from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.tables import ClusterRun, Topic
from app.services.clustering import (
    _cluster_messages,
    _growth_rate,
    run_cluster_batch,
    topic_to_summary,
)


def test_cluster_messages_groups_repeated_terms() -> None:
    now = datetime.now(UTC)
    setup_id = uuid4()
    billing_id = uuid4()
    messages = [
        {
            "message_id": setup_id,
            "conversation_id": uuid4(),
            "content": "Setup API key keeps failing before onboarding can finish.",
            "sentiment_score": -0.5,
            "sentiment_label": "negative",
            "created_at": now - timedelta(hours=20),
            "embedding": [0.1, 0.2, 0.3],
        },
        {
            "message_id": uuid4(),
            "conversation_id": uuid4(),
            "content": "API key setup is blocked and onboarding cannot continue.",
            "sentiment_score": -0.5,
            "sentiment_label": "negative",
            "created_at": now - timedelta(hours=2),
            "embedding": [0.1, 0.2, 0.3],
        },
        {
            "message_id": billing_id,
            "conversation_id": uuid4(),
            "content": "Billing upgrade invoice sync is confusing but support helped.",
            "sentiment_score": 0.5,
            "sentiment_label": "positive",
            "created_at": now - timedelta(hours=1),
            "embedding": [0.8, 0.2, 0.1],
        },
    ]

    clusters = _cluster_messages(messages, min_cluster_size=2)

    assert len(clusters) >= 2
    assert any(
        {"setup", "onboarding"} <= set(cluster.terms or []) for cluster in clusters
    )
    assert any(billing_id in cluster.message_ids for cluster in clusters)


def test_topic_to_summary_serializes_public_contract() -> None:
    cluster_run_id = uuid4()
    topic = Topic(
        id=uuid4(),
        project_id="project-1",
        cluster_run_id=cluster_run_id,
        cluster_label=2,
        label="api / setup / onboarding",
        summary="Setup API key keeps failing before onboarding can finish",
        terms=["api", "setup", "onboarding"],
        member_count=4,
        growth_24h=1.0,
        growth_7d=0.5,
        sentiment_mean=-0.25,
        negative_sentiment_share=0.75,
        first_seen_at=datetime.now(UTC) - timedelta(days=1),
        last_seen_at=datetime.now(UTC),
    )

    summary = topic_to_summary(topic)

    assert summary["id"] == str(topic.id)
    assert summary["cluster_run_id"] == str(cluster_run_id)
    assert summary["label"] == "api / setup / onboarding"
    assert summary["representative_examples"] == ["api", "setup", "onboarding"]


def test_growth_rate_consecutive_equal_windows() -> None:
    now = datetime.now(UTC)
    messages = [
        {"created_at": now - timedelta(hours=4)},
        {"created_at": now - timedelta(hours=12)},
        {"created_at": now - timedelta(hours=28)},
        {"created_at": now - timedelta(hours=36)},
    ]
    rate = _growth_rate(messages, hours=24)
    assert rate is not None
    assert rate == 0.0


def test_growth_rate_growing_topic() -> None:
    now = datetime.now(UTC)
    messages = [
        {"created_at": now - timedelta(hours=1)},
        {"created_at": now - timedelta(hours=3)},
        {"created_at": now - timedelta(hours=6)},
        {"created_at": now - timedelta(hours=25)},
    ]
    rate = _growth_rate(messages, hours=24)
    assert rate is not None
    assert rate == 2.0


def test_growth_rate_returns_none_when_no_older_window() -> None:
    now = datetime.now(UTC)
    messages = [
        {"created_at": now - timedelta(hours=1)},
        {"created_at": now - timedelta(hours=5)},
    ]
    rate = _growth_rate(messages, hours=24)
    assert rate is None


def test_growth_rate_returns_none_for_single_message() -> None:
    messages = [{"created_at": datetime.now(UTC)}]
    rate = _growth_rate(messages, hours=24)
    assert rate is None


@pytest.mark.asyncio
async def test_run_cluster_batch_failure_marks_run_as_failed(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    from unittest.mock import patch

    async with session_factory() as session:
        with patch(
            "app.services.clustering._cluster_messages",
            side_effect=ValueError("simulated failure"),
        ):
            with pytest.raises(ValueError, match="simulated failure"):
                await run_cluster_batch(
                    session,
                    "project-1",
                )

    async with session_factory() as session:
        runs = (
            await session.execute(
                select(ClusterRun)
                .where(ClusterRun.project_id == "project-1")
                .order_by(ClusterRun.created_at.desc())
            )
        ).scalars().all()

    assert len(runs) >= 1
    assert runs[0].status == "failed"
    assert "simulated failure" in (runs[0].error_message or "")
