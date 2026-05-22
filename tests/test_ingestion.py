import sqlite3

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.db import Base
from app.models.schemas import ConversationIngestRequest
from app.models.tables import Conversation, ProcessingJob, Project
from app.services.ingestion import (
    conversation_content_hash,
    enqueue_conversation_ingest,
)


class FakeJob:
    job_id = "queued-job-1"


class FakeRedis:
    async def enqueue_job(self, *args: object, **kwargs: object) -> FakeJob:
        return FakeJob()

    async def aclose(self) -> None:
        return None


async def fake_queue_factory() -> FakeRedis:
    return FakeRedis()


@pytest_asyncio.fixture
async def session_factory():
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        creator=lambda: sqlite3.connect(  # noqa: E731
            ":memory:",
            check_same_thread=False,
        ),
        poolclass=StaticPool,
    )
    async with engine.begin() as connection:
        await connection.run_sync(
            Base.metadata.create_all,
            tables=[Project.__table__, Conversation.__table__, ProcessingJob.__table__],
        )
    try:
        yield async_sessionmaker(engine, expire_on_commit=False)
    finally:
        await engine.dispose()


def sample_payload(conversation_id: str = "conv-1") -> ConversationIngestRequest:
    return ConversationIngestRequest(
        project_id="project-1",
        conversation_id=conversation_id,
        messages=[
            {
                "role": "user",
                "content": "I keep getting blocked during setup.",
            },
            {
                "role": "assistant",
                "content": "Can you share the error message?",
            },
        ],
        metadata={"source": "test"},
    )


def test_conversation_content_hash_ignores_metadata() -> None:
    first = sample_payload()
    second = sample_payload()
    second.metadata["source"] = "changed"

    assert conversation_content_hash(first) == conversation_content_hash(second)


@pytest.mark.asyncio
async def test_ingest_persists_project_conversation_and_job(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        response = await enqueue_conversation_ingest(
            sample_payload(),
            session,
            queue_factory=fake_queue_factory,
        )

        assert response.status == "accepted"
        assert response.job_id is not None
        assert response.stored_conversation_id is not None

    async with session_factory() as session:
        project = await session.get(Project, "project-1")
        conversations = (await session.execute(select(Conversation))).scalars().all()
        jobs = (await session.execute(select(ProcessingJob))).scalars().all()

    assert project is not None
    assert len(conversations) == 1
    assert conversations[0].external_id == "conv-1"
    assert conversations[0].metadata_ == {"source": "test"}
    assert len(jobs) == 1
    assert jobs[0].job_type == "process_conversation"
    assert jobs[0].status == "queued"


@pytest.mark.asyncio
async def test_ingest_dedupes_by_external_id(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        first = await enqueue_conversation_ingest(
            sample_payload(),
            session,
            queue_factory=fake_queue_factory,
        )
        second = await enqueue_conversation_ingest(
            sample_payload(),
            session,
            queue_factory=fake_queue_factory,
        )

        conversations = (await session.execute(select(Conversation))).scalars().all()
        jobs = (await session.execute(select(ProcessingJob))).scalars().all()

    assert first.status == "accepted"
    assert second.status == "duplicate"
    assert second.stored_conversation_id == first.stored_conversation_id
    assert len(conversations) == 1
    assert len(jobs) == 1


@pytest.mark.asyncio
async def test_ingest_dedupes_by_content_hash(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        first = await enqueue_conversation_ingest(
            sample_payload("conv-1"),
            session,
            queue_factory=fake_queue_factory,
        )
        second = await enqueue_conversation_ingest(
            sample_payload("conv-2"),
            session,
            queue_factory=fake_queue_factory,
        )

        conversations = (await session.execute(select(Conversation))).scalars().all()
        jobs = (await session.execute(select(ProcessingJob))).scalars().all()

    assert first.status == "accepted"
    assert second.status == "duplicate"
    assert second.stored_conversation_id == first.stored_conversation_id
    assert len(conversations) == 1
    assert len(jobs) == 1
