from typing import cast
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models.schemas import (
    MessageRole,
    TopicDetailResponse,
    TopicListResponse,
    TopicMessageExample,
    TopicSummary,
)
from app.services.clustering import (
    latest_cluster_run,
    load_topic_detail,
    load_topics,
    topic_to_summary,
)

router = APIRouter()


@router.get("/topics", response_model=TopicListResponse)
async def list_topics(
    project_id: str,
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> TopicListResponse:
    run = await latest_cluster_run(session, project_id)
    topics = await load_topics(session, project_id, run.id if run is not None else None)
    return TopicListResponse(
        project_id=project_id,
        latest_cluster_run_id=str(run.id) if run is not None else None,
        topics=[
            TopicSummary.model_validate(topic_to_summary(topic)) for topic in topics
        ],
    )


@router.get("/topics/{topic_id}", response_model=TopicDetailResponse)
async def get_topic(
    topic_id: str,
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> TopicDetailResponse:
    try:
        topic_uuid = UUID(topic_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="topic not found"
        ) from exc

    topic, memberships, messages = await load_topic_detail(session, topic_uuid)
    if topic is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="topic not found"
        )

    representative_examples = [message.content for message in messages[:3]]
    topic_data = topic_to_summary(topic)
    topic_data.pop("representative_examples", None)
    return TopicDetailResponse(
        project_id=topic.project_id,
        source_conversation_ids=[str(message.conversation_id) for message in messages],
        messages=[
            TopicMessageExample(
                message_id=str(message.id),
                conversation_id=str(message.conversation_id),
                role=cast(MessageRole, message.role),
                content=message.content,
                similarity=next(
                    (
                        membership.similarity
                        for membership in memberships
                        if membership.message_id == message.id
                    ),
                    None,
                ),
                sentiment_score=message.sentiment_score,
                sentiment_label=message.sentiment_label,
                created_at=message.created_at,
            )
            for message in messages
        ],
        representative_examples=representative_examples,
        **topic_data,
    )
