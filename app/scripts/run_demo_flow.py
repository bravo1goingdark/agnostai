from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

from app.db import SessionLocal
from app.services.clustering import compute_insights, run_cluster_batch
from app.services.reports import write_current_topic_report
from app.services.sample_data import seed_sample_conversations


async def _run(project_id: str) -> int:
    report_dir = Path(os.environ.get("REPORT_DIR", "reports"))
    async with SessionLocal() as session:
        seed_result = await seed_sample_conversations(session, project_id)
        cluster_result = await run_cluster_batch(session, project_id)
        insights = await compute_insights(session, project_id)
        report_path = await write_current_topic_report(
            session,
            project_id,
            output_dir=report_dir,
        )

    print(
        "demo_flow_complete "
        f"project={project_id} "
        f"accepted={seed_result.accepted} "
        f"duplicates={seed_result.duplicate} "
        f"processed={seed_result.processed} "
        f"cluster_run={cluster_result.cluster_run.id} "
        f"topics={len(cluster_result.topics)} "
        f"total_messages={insights['total_messages']} "
        f"report={report_path}"
    )
    return 0


def main() -> None:
    project_id = sys.argv[1] if len(sys.argv) >= 2 else "project-1"
    raise SystemExit(asyncio.run(_run(project_id)))


if __name__ == "__main__":
    main()
