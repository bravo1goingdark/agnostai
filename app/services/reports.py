from pathlib import Path
from typing import TYPE_CHECKING

from app.services.clustering import latest_cluster_run, load_topics

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


def render_topic_report(
    project_id: str,
    topics: list[dict[str, object]],
    cluster_run_id: str | None = None,
) -> str:
    lines = ["# Agnost Insights Report", "", f"Project: {project_id}", ""]
    if cluster_run_id is not None:
        lines.extend([f"Latest cluster run: {cluster_run_id}", ""])
    if not topics:
        lines.append(
            "No cluster run available."
            if cluster_run_id is None
            else "No topics found in latest cluster run."
        )
        return "\n".join(lines).strip() + "\n"

    lines.append("Top topics:")
    for topic in topics:
        label = str(topic.get("label", "topic"))
        member_count = topic.get("member_count", 0)
        summary = topic.get("summary")
        lines.append(f"- {label} ({member_count} messages)")
        if summary:
            lines.append(f"  - {summary}")
    return "\n".join(lines).strip() + "\n"


async def render_current_topic_report(
    session: "AsyncSession",
    project_id: str,
) -> str:
    run = await latest_cluster_run(session, project_id)
    topics = await load_topics(session, project_id, run.id if run is not None else None)
    return render_topic_report(
        project_id,
        [
            {
                "label": topic.label,
                "member_count": topic.member_count,
                "summary": topic.summary,
            }
            for topic in topics
        ],
        cluster_run_id=str(run.id) if run is not None else None,
    )


async def write_current_topic_report(
    session: "AsyncSession",
    project_id: str,
    *,
    output_dir: Path | str = "reports",
) -> Path:
    import os

    output_dir = os.environ.get("REPORT_DIR", str(output_dir))
    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True)
    report_file = output_path / f"{project_id}-insights.md"
    report_file.write_text(
        await render_current_topic_report(session, project_id),
        encoding="utf-8",
    )
    return report_file
