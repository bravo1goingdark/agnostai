from datetime import UTC

from app.services.insights import empty_insights
from app.services.reports import render_topic_report


def test_empty_insights_has_current_contract() -> None:
    result = empty_insights("project-1")

    assert result["project_id"] == "project-1"
    assert result["latest_cluster_run_id"] is None
    assert result["total_topics"] == 0
    assert result["generated_at"].tzinfo is UTC


def test_render_topic_report_includes_run_and_topics() -> None:
    report = render_topic_report(
        "project-1",
        [{"label": "setup", "member_count": 3, "summary": "Setup is failing"}],
        cluster_run_id="run-1",
    )

    assert "Latest cluster run: run-1" in report
    assert "setup (3 messages)" in report


def test_render_topic_report_empty_topics_no_run() -> None:
    report = render_topic_report(
        "project-1",
        [],
        cluster_run_id=None,
    )

    assert "No cluster run available." in report


def test_render_topic_report_empty_topics_with_run() -> None:
    report = render_topic_report(
        "project-1",
        [],
        cluster_run_id="run-1",
    )

    assert "No topics found in latest cluster run." in report
