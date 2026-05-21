from fastapi import APIRouter, HTTPException, status

router = APIRouter()


@router.get("/topics")
async def list_topics(project_id: str) -> dict[str, object]:
    return {"project_id": project_id, "topics": []}


@router.get("/topics/{topic_id}")
async def get_topic(topic_id: str) -> dict[str, object]:
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"topic {topic_id!r} has not been clustered yet",
    )

