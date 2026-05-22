from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from app.db import SessionLocal
from app.models.tables import Project
from app.services.reports import write_current_topic_report


async def _export(project_id: str) -> int:
    async with SessionLocal() as session:
        project = await session.get(Project, project_id)
        if project is None:
            raise SystemExit(f"project {project_id!r} does not exist")
        report_file = await write_current_topic_report(
            session,
            project_id,
            output_dir=Path("reports"),
        )
        print(report_file)
        print(report_file.read_text(encoding="utf-8"))
        return 0


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit("usage: agnost-export-report PROJECT_ID")
    raise SystemExit(asyncio.run(_export(sys.argv[1])))


if __name__ == "__main__":
    main()
