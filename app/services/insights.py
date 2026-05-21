from __future__ import annotations

from datetime import UTC, datetime


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
    }


def summarize_queue_metrics(*, queued_jobs: int, failed_jobs: int) -> dict[str, int]:
    return {
        "queued_jobs": queued_jobs,
        "failed_jobs": failed_jobs,
    }
