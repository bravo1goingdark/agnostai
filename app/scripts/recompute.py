from __future__ import annotations

import asyncio
import sys

from sqlalchemy import delete, select

from app.db import SessionLocal
from app.models.tables import (
    Conversation,
    Message,
    MessageEmbedding,
    Topic,
    TopicMembership,
)
from app.services.clustering import run_cluster_batch
from app.workers.jobs import process_conversation


async def _recompute(project_id: str) -> int:
    async with SessionLocal() as session:
        conversations_result = await session.execute(
            select(Conversation.id).where(Conversation.project_id == project_id)
        )
        conversation_ids = [
            row[0] for row in conversations_result.all()
        ]
        if not conversation_ids:
            print(f"project={project_id} status=no_conversations")
            return 0

        await session.execute(
            delete(TopicMembership).where(
                TopicMembership.project_id == project_id
            )
        )
        await session.execute(
            delete(Topic).where(Topic.project_id == project_id)
        )
        await session.execute(
            delete(MessageEmbedding).where(
                MessageEmbedding.project_id == project_id
            )
        )
        await session.execute(
            delete(Message).where(Message.project_id == project_id)
        )
        await session.commit()

        processed = 0
        for conversation_id in conversation_ids:
            await process_conversation(
                {"session": session},
                project_id,
                str(conversation_id),
            )
            processed += 1

        print(
            f"project={project_id} "
            f"reprocessed_conversations={processed}"
        )

        cluster_result = await run_cluster_batch(session, project_id)
        print(
            f"project={project_id} "
            f"cluster_run={cluster_result.cluster_run.id} "
            f"topics={len(cluster_result.topics)}"
        )

    return 0


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit("usage: agnost-recompute PROJECT_ID")
    raise SystemExit(asyncio.run(_recompute(sys.argv[1])))


if __name__ == "__main__":
    main()
