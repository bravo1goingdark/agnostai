from fastapi import APIRouter

router = APIRouter()


@router.get("/insights")
async def get_insights(project_id: str) -> dict[str, object]:
    return {
        "project_id": project_id,
        "topics": [],
        "sentiment_distribution": {},
        "emerging_topics": [],
    }

