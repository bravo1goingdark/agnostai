from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.schemas import ConversationIngestRequest, ConversationIngestResponse


async def enqueue_conversation_ingest(
    payload: ConversationIngestRequest,
    session: AsyncSession,
) -> ConversationIngestResponse:
    """Accept a conversation for processing.

    Phase 1 keeps this as a contract stub. Phase 2 will persist raw records and
    enqueue an ARQ job after the schema and migrations are in place.
    """
    _ = session
    return ConversationIngestResponse(
        project_id=payload.project_id,
        conversation_id=payload.conversation_id,
        status="accepted",
        job_id=str(uuid4()),
    )

