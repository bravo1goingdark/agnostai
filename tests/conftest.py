import sqlite3

import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.db import Base
from app.models.tables import (
    ClusterRun,
    Conversation,
    Message,
    MessageEmbedding,
    ProcessingJob,
    Project,
    Topic,
    TopicMembership,
)


class FakeJob:
    def __init__(self, job_id: str = "queued-job-1") -> None:
        self.job_id = job_id


class FakeRedis:
    def __init__(self) -> None:
        self.enqueued: list[tuple[str, tuple[object, ...]]] = []

    async def enqueue_job(
        self,
        function: str,
        *args: object,
        **kwargs: object,
    ) -> FakeJob:
        self.enqueued.append((function, args))
        return FakeJob("queued-job-1")

    async def aclose(self) -> None:
        return None


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
            tables=[
                Project.__table__,
                Conversation.__table__,
                Message.__table__,
                MessageEmbedding.__table__,
                ClusterRun.__table__,
                Topic.__table__,
                TopicMembership.__table__,
                ProcessingJob.__table__,
            ],
        )
    try:
        yield async_sessionmaker(engine, expire_on_commit=False)
    finally:
        await engine.dispose()
