import logging
from collections.abc import Sequence
from hashlib import sha256
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings
from app.models.tables import Conversation, Message, MessageEmbedding, ProcessingJob
from app.services.embeddings import embed_text_stub, embedding_metadata
from app.services.normalization import (
    analysis_text_for_message,
    normalize_message_text,
    parse_conversation_messages,
)
from app.services.pii import redact_obvious_pii
from app.services.sentiment import is_user_message, score_sentiment_stub

logger = logging.getLogger(__name__)

_settings = get_settings()
_engine = create_async_engine(_settings.database_url, pool_pre_ping=True)
SessionLocal = async_sessionmaker(_engine, expire_on_commit=False)


async def process_conversation(
    ctx: dict[str, object],
    project_id: str,
    conversation_id: str,
) -> None:
    session = _session_from_ctx(ctx)
    if session is None:
        async with SessionLocal() as session_obj:
            await _process_conversation(session_obj, project_id, conversation_id)
        return

    await _process_conversation(session, project_id, conversation_id)


async def _process_conversation(
    session: AsyncSession,
    project_id: str,
    conversation_id: str,
) -> None:
    job = await _load_processing_job(session, project_id, conversation_id)
    if job is not None and job.status in {"completed", "processing"}:
        logger.info(
            "process_conversation_skipped project_id=%s conversation_id=%s status=%s",
            project_id,
            conversation_id,
            job.status,
        )
        return

    if job is not None:
        job.status = "processing"
    conversation = await _load_conversation(session, project_id, conversation_id)
    if conversation is None:
        logger.warning(
            "process_conversation_missing_conversation "
            "project_id=%s conversation_id=%s",
            project_id,
            conversation_id,
        )
        return
    await _materialize_messages(session, conversation)
    derived_messages = await _load_messages(session, project_id, conversation_id)
    metadata = embedding_metadata()

    for message in derived_messages:
        normalized = normalize_message_text(message.content)
        cleaned = redact_obvious_pii(normalized)
        sentiment_score, sentiment_label = score_sentiment_stub(cleaned)
        message.content = cleaned
        message.normalized_text_hash = sha256(cleaned.encode("utf-8")).hexdigest()
        if is_user_message(message.role):
            message.sentiment_score = sentiment_score
            message.sentiment_label = sentiment_label
        session.add(
            MessageEmbedding(
                project_id=project_id,
                message_id=message.id,
                model_name=str(metadata["model_name"]),
                dimension=metadata["dimension"],
                embedding=embed_text_stub(cleaned, metadata["dimension"]),
            )
        )

    if job is not None:
        job.status = "completed"

    await session.commit()
    logger.info(
        "process_conversation_complete "
        "project_id=%s conversation_id=%s message_count=%s",
        project_id,
        conversation_id,
        len(derived_messages),
    )


async def _load_processing_job(
    session: AsyncSession,
    project_id: str,
    conversation_id: str,
) -> ProcessingJob | None:
    result = await session.execute(
        select(ProcessingJob)
        .where(ProcessingJob.project_id == project_id)
        .where(ProcessingJob.conversation_id == UUID(conversation_id))
    )
    return result.scalar_one_or_none()


async def _load_messages(
    session: AsyncSession,
    project_id: str,
    conversation_id: str,
) -> Sequence[Message]:
    result = await session.execute(
        select(Message)
        .where(Message.project_id == project_id)
        .where(Message.conversation_id == UUID(conversation_id))
        .order_by(Message.sequence_index.asc())
    )
    return list(result.scalars().all())


async def _load_conversation(
    session: AsyncSession,
    project_id: str,
    conversation_id: str,
) -> Conversation | None:
    result = await session.execute(
        select(Conversation)
        .where(Conversation.project_id == project_id)
        .where(Conversation.id == UUID(conversation_id))
    )
    return result.scalar_one_or_none()


async def _materialize_messages(
    session: AsyncSession,
    conversation: Conversation,
) -> list[Message]:
    existing = await _load_messages(
        session,
        conversation.project_id,
        str(conversation.id),
    )
    if existing:
        return list(existing)

    messages = parse_conversation_messages(conversation.raw_payload)
    previous_assistant_context: str | None = None
    materialized: list[Message] = []
    for index, raw_message in enumerate(messages):
        analysis_text = analysis_text_for_message(
            raw_message,
            previous_assistant_context,
        )
        normalized = normalize_message_text(analysis_text)
        cleaned = redact_obvious_pii(normalized)
        materialized.append(
            Message(
                project_id=conversation.project_id,
                conversation_id=conversation.id,
                external_id=raw_message.message_id,
                sequence_index=index,
                role=raw_message.role,
                content=cleaned,
                normalized_text_hash=sha256(cleaned.encode("utf-8")).hexdigest(),
                created_at=raw_message.created_at,
                metadata_=raw_message.metadata,
            )
        )
        if raw_message.role == "assistant":
            previous_assistant_context = cleaned

    session.add_all(materialized)
    await session.flush()
    return materialized


def prepare_message_rows(conversation: Conversation) -> list[Message]:
    messages = parse_conversation_messages(conversation.raw_payload)
    previous_assistant_context: str | None = None
    rows: list[Message] = []
    for index, raw_message in enumerate(messages):
        analysis_text = analysis_text_for_message(
            raw_message,
            previous_assistant_context,
        )
        normalized = normalize_message_text(analysis_text)
        cleaned = redact_obvious_pii(normalized)
        rows.append(
            Message(
                project_id=conversation.project_id,
                conversation_id=conversation.id,
                external_id=raw_message.message_id,
                sequence_index=index,
                role=raw_message.role,
                content=cleaned,
                normalized_text_hash=sha256(cleaned.encode("utf-8")).hexdigest(),
                created_at=raw_message.created_at,
                metadata_=raw_message.metadata,
            )
        )
        if raw_message.role == "assistant":
            previous_assistant_context = cleaned
    return rows


def _session_from_ctx(ctx: dict[str, object]) -> AsyncSession | None:
    maybe_session = ctx.get("session")
    if isinstance(maybe_session, AsyncSession):
        return maybe_session
    return None
