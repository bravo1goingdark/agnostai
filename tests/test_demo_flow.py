import sqlite3
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
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
from app.services.clustering import compute_insights, run_cluster_batch
from app.services.reports import write_current_topic_report
from app.services.sample_data import sample_payloads, seed_sample_conversations


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
                ProcessingJob.__table__,
                ClusterRun.__table__,
                Topic.__table__,
                TopicMembership.__table__,
            ],
        )
    try:
        yield async_sessionmaker(engine, expire_on_commit=False)
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_sample_data_runs_to_insights_and_report(
    session_factory: async_sessionmaker[AsyncSession],
    tmp_path: Path,
) -> None:
    async with session_factory() as session:
        expected_count = len(sample_payloads("project-1"))
        seed_result = await seed_sample_conversations(session, "project-1")
        cluster_result = await run_cluster_batch(session, "project-1")
        insights = await compute_insights(session, "project-1")
        report_path = await write_current_topic_report(
            session,
            "project-1",
            output_dir=tmp_path,
        )

        jobs = (await session.execute(select(ProcessingJob))).scalars().all()

    assert seed_result.accepted == expected_count
    assert seed_result.processed == expected_count
    assert {job.status for job in jobs} == {"completed"}
    assert len(cluster_result.topics) >= 3
    assert len(cluster_result.memberships) == expected_count
    assert insights["total_messages"] == expected_count * 2
    assert insights["total_topics"] == len(cluster_result.topics)
    report = report_path.read_text(encoding="utf-8")
    assert "Top topics:" in report
    assert "setup" in report.lower()
