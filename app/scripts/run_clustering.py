from __future__ import annotations

import asyncio
import sys
from datetime import datetime

from app.db import SessionLocal
from app.models.tables import Project
from app.services.clustering import run_cluster_batch


async def _run(
    project_id: str,
    window_start: datetime | None = None,
    window_end: datetime | None = None,
) -> int:
    async with SessionLocal() as session:
        project = await session.get(Project, project_id)
        if project is None:
            raise SystemExit(f"project {project_id!r} does not exist")
        result = await run_cluster_batch(
            session,
            project_id,
            window_start=window_start,
            window_end=window_end,
        )
        print(
            "cluster_run="
            f"{result.cluster_run.id} "
            f"topics={len(result.topics)} "
            f"memberships={len(result.memberships)}"
        )
    return 0


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit("usage: agnost-run-clustering PROJECT_ID")
    raise SystemExit(asyncio.run(_run(sys.argv[1])))


if __name__ == "__main__":
    main()
