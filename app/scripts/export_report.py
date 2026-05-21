from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from app.db import SessionLocal
from app.models.tables import Project
from app.services.clustering import latest_cluster_run, load_topics


async def _export(project_id: str) -> str:
    async with SessionLocal() as session:
        project = await session.get(Project, project_id)
        if project is None:
            raise SystemExit(f"project {project_id!r} does not exist")
        run = await latest_cluster_run(session, project_id)
        topics = await load_topics(
            session, project_id, run.id if run is not None else None
        )
        lines = ["# Agnost Insights Report", "", f"Project: {project_id}", ""]
        if run is None:
            lines.append("No cluster run available.")
        else:
            lines.append(f"Latest cluster run: {run.id}")
            lines.append("")
            for topic in topics:
                lines.append(f"- {topic.label} ({topic.member_count} messages)")
                if topic.summary:
                    lines.append(f"  - {topic.summary}")
        report = "\n".join(lines).strip() + "\n"
        output_path = Path("reports")
        output_path.mkdir(exist_ok=True)
        report_file = output_path / f"{project_id}-insights.md"
        report_file.write_text(report, encoding="utf-8")
        print(report_file)
        return report


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit("usage: agnost-export-report PROJECT_ID")
    raise SystemExit(asyncio.run(_export(sys.argv[1])))


if __name__ == "__main__":
    main()
