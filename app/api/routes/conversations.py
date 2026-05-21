from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models.schemas import ConversationIngestRequest, ConversationIngestResponse
from app.services.ingestion import enqueue_conversation_ingest

router = APIRouter()


@router.post(
    "/conversations",
    response_model=ConversationIngestResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def ingest_conversation(
    payload: ConversationIngestRequest,
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> ConversationIngestResponse:
    return await enqueue_conversation_ingest(payload, session)
