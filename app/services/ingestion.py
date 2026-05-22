from hashlib import sha256
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.schemas import ConversationIngestRequest, ConversationIngestResponse
from app.models.tables import Conversation, ProcessingJob, Project
from app.workers.queue import (
    QueueFactory,
    create_queue,
    enqueue_process_conversation_via_factory,
)


async def enqueue_conversation_ingest(
    payload: ConversationIngestRequest,
    session: AsyncSession,
    queue_factory: QueueFactory | None = None,
) -> ConversationIngestResponse:
    """Persist raw conversation input and record a queued processing job."""
    content_hash = conversation_content_hash(payload)
    await _ensure_project(session, payload.project_id)

    existing = await _find_existing_conversation(session, payload, content_hash)
    if existing is not None:
        job = await _find_latest_processing_job(session, existing.id)
        return ConversationIngestResponse(
            project_id=payload.project_id,
            conversation_id=payload.conversation_id,
            status="duplicate",
            job_id=str(job.id) if job is not None else None,
            stored_conversation_id=str(existing.id),
        )

    conversation = Conversation(
        project_id=payload.project_id,
        external_id=payload.conversation_id,
        content_hash=content_hash,
        raw_payload=payload.model_dump(mode="json"),
        metadata_=payload.metadata,
    )
    session.add(conversation)
    await session.flush()

    job = ProcessingJob(
        project_id=payload.project_id,
        conversation_id=conversation.id,
        job_type="process_conversation",
        status="queued",
    )
    session.add(job)
    await session.commit()

    try:
        job_id = await enqueue_process_conversation_via_factory(
            queue_factory if queue_factory is not None else create_queue,
            payload.project_id,
            str(conversation.id),
        )
    except Exception as exc:
        job.status = "failed"
        job.last_error = str(exc)
        await session.commit()
        raise

    if job_id is not None:
        job.arq_job_id = job_id
        await session.commit()

    return ConversationIngestResponse(
        project_id=payload.project_id,
        conversation_id=payload.conversation_id,
        status="accepted",
        job_id=job_id or str(job.id),
        stored_conversation_id=str(conversation.id),
    )


def conversation_content_hash(payload: ConversationIngestRequest) -> str:
    """Stable hash over the conversational signal, excluding volatile metadata."""
    parts: list[str] = []
    for message in payload.messages:
        normalized_content = " ".join(message.content.split())
        parts.append(f"{message.role}:{normalized_content}")
    return sha256("\n".join(parts).encode("utf-8")).hexdigest()


async def _ensure_project(session: AsyncSession, project_id: str) -> None:
    project = await session.get(Project, project_id)
    if project is None:
        session.add(Project(id=project_id, metadata_={}))
        await session.flush()


async def _find_existing_conversation(
    session: AsyncSession,
    payload: ConversationIngestRequest,
    content_hash: str,
) -> Conversation | None:
    result = await session.execute(
        select(Conversation)
        .where(Conversation.project_id == payload.project_id)
        .where(Conversation.external_id == payload.conversation_id)
    )
    existing = result.scalar_one_or_none()
    if existing is not None:
        return existing

    result = await session.execute(
        select(Conversation)
        .where(Conversation.project_id == payload.project_id)
        .where(Conversation.content_hash == content_hash)
    )
    return result.scalar_one_or_none()


async def _find_latest_processing_job(
    session: AsyncSession,
    conversation_id: UUID,
) -> ProcessingJob | None:
    result = await session.execute(
        select(ProcessingJob)
        .where(ProcessingJob.conversation_id == conversation_id)
        .order_by(ProcessingJob.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()
