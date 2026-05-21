from __future__ import annotations

import asyncio
import sys
from datetime import UTC, datetime, timedelta

from app.db import SessionLocal
from app.models.schemas import ConversationIngestRequest
from app.models.tables import Project
from app.services.ingestion import enqueue_conversation_ingest


def _sample_payloads(project_id: str) -> list[ConversationIngestRequest]:
    now = datetime.now(UTC)
    return [
        ConversationIngestRequest(
            project_id=project_id,
            conversation_id="sample-setup-1",
            messages=[
                {
                    "role": "user",
                    "content": "The setup keeps failing on the API key step.",
                    "created_at": now - timedelta(hours=8),
                },
                {
                    "role": "assistant",
                    "content": "Try regenerating the key and run the installer again.",
                    "created_at": now - timedelta(hours=8, minutes=-5),
                },
            ],
            metadata={"source": "sample"},
        ),
        ConversationIngestRequest(
            project_id=project_id,
            conversation_id="sample-billing-1",
            messages=[
                {
                    "role": "user",
                    "content": "Billing is broken after the upgrade and I'm blocked.",
                    "created_at": now - timedelta(hours=2),
                },
                {
                    "role": "assistant",
                    "content": "Thanks, we'll look into the failed invoice sync.",
                    "created_at": now - timedelta(hours=2, minutes=-3),
                },
            ],
            metadata={"source": "sample"},
        ),
    ]


async def _seed(project_id: str) -> int:
    async with SessionLocal() as session:
        project = await session.get(Project, project_id)
        if project is None:
            session.add(Project(id=project_id, metadata_={"seeded": True}))
            await session.commit()
        for payload in _sample_payloads(project_id):
            await enqueue_conversation_ingest(
                payload,
                session,
                queue_factory=_queue_factory,
            )
    return 0


class _NullQueue:
    async def enqueue_job(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        class _Job:
            job_id = "sample-job"

        return _Job()

    async def aclose(self) -> None:
        return None


async def _queue_factory() -> _NullQueue:
    return _NullQueue()


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit("usage: agnost-seed-sample-data PROJECT_ID")
    raise SystemExit(asyncio.run(_seed(sys.argv[1])))


if __name__ == "__main__":
    main()
