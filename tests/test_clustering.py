from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from app.models.tables import Topic
from app.services.clustering import _cluster_messages, topic_to_summary


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
