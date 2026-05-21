from __future__ import annotations

import asyncio
import sys

from app.db import SessionLocal
from app.services.sample_data import seed_sample_conversations


async def _seed(project_id: str) -> int:
    async with SessionLocal() as session:
        result = await seed_sample_conversations(session, project_id)
        print(
            "seeded "
            f"project={result.project_id} "
            f"accepted={result.accepted} "
            f"duplicates={result.duplicate} "
            f"processed={result.processed}"
        )
    return 0


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit("usage: agnost-seed-sample-data PROJECT_ID")
    raise SystemExit(asyncio.run(_seed(sys.argv[1])))


if __name__ == "__main__":
    main()
