import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.schemas import ConversationIngestRequest
from app.models.tables import (
    Message,
    MessageEmbedding,
    ProcessingJob,
)
from app.services.ingestion import enqueue_conversation_ingest
from app.workers.jobs import process_conversation
from tests.conftest import FakeRedis


def sample_payload() -> ConversationIngestRequest:
    return ConversationIngestRequest(
        project_id="project-1",
        conversation_id="conversation-1",
        messages=[
            {"role": "assistant", "content": "Thanks for reaching out."},
            {
                "role": "user",
                "content": "I am blocked by a broken setup step.",
            },
            {"role": "assistant", "content": "Can you share the exact error?"},
        ],
        metadata={"source": "worker-test"},
    )


@pytest.mark.asyncio
async def test_ingest_enqueues_single_job_with_fake_queue(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    fake_redis = FakeRedis()

    async def fake_queue_factory():
        return fake_redis

    async with session_factory() as session:
        response = await enqueue_conversation_ingest(
            sample_payload(),
            session,
            queue_factory=fake_queue_factory,
        )

    assert response.status == "accepted"
    assert response.job_id == "queued-job-1"
    assert fake_redis.enqueued == [
        ("process_conversation", ("project-1", response.stored_conversation_id))
    ]


@pytest.mark.asyncio
async def test_worker_materializes_messages_and_embeddings(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        async def fake_queue_factory():
            return FakeRedis()

        ingest_response = await enqueue_conversation_ingest(
            sample_payload(),
            session,
            queue_factory=fake_queue_factory,
        )

        await process_conversation(
            {"session": session},
            "project-1",
            ingest_response.stored_conversation_id or "",
        )

        messages = (await session.execute(select(Message))).scalars().all()
        embeddings = (await session.execute(select(MessageEmbedding))).scalars().all()
        job = (await session.execute(select(ProcessingJob))).scalars().first()

    assert len(messages) == 3
    assert messages[1].sentiment_label == "negative"
    assert len(embeddings) == 3
    assert job is not None
    assert job.status == "completed"
