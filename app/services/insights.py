from __future__ import annotations

from datetime import UTC, datetime
from typing import Any


def empty_insights(project_id: str) -> dict[str, object]:
    return {
        "project_id": project_id,
        "latest_cluster_run_id": None,
        "generated_at": datetime.now(UTC),
        "total_messages": 0,
        "total_topics": 0,
        "top_topics": [],
        "sentiment_distribution": {},
        "emerging_topics": [],
        "narrative_insights": [],
    }


def generate_narrative_insights(insights: dict[str, Any]) -> list[str]:
    """Template structured topic data into PM-readable prose sentences."""
    sentences: list[str] = []
    total = insights.get("total_messages", 0)
    top_topics: list[dict[str, Any]] = insights.get("top_topics", [])
    emerging: list[dict[str, Any]] = insights.get("emerging_topics", [])

    for topic in top_topics[:3]:
        label = topic.get("label", "unknown")
        count = topic.get("member_count", 0)
        neg_share = topic.get("negative_sentiment_share")

        # Volume signal
        if total > 0:
            pct = round(count / total * 100)
            sentences.append(
                f"{pct}% of user messages cluster around \"{label}\" "
                f"({count} of {total} messages)"
            )

        # Sentiment alert
        if neg_share is not None and neg_share >= 0.4:
            sentences.append(
                f"Topic \"{label}\" has {round(neg_share * 100)}% negative "
                f"sentiment — potential pain point"
            )

    # Emerging / feature request signals
    for topic in emerging[:2]:
        label = topic.get("label", "unknown")
        growth = topic.get("growth_24h")
        count = topic.get("member_count", 0)
        sentiment_mean = topic.get("sentiment_mean")

        if growth is not None and growth > 0:
            if sentiment_mean is not None and sentiment_mean >= 0.0:
                sentences.append(
                    f"Possible feature request: \"{label}\" "
                    f"({count} mentions, growing)"
                )
            else:
                sentences.append(
                    f"Emerging concern: \"{label}\" "
                    f"(↑{round(growth * 100)}% in 24h)"
                )

    return sentences
