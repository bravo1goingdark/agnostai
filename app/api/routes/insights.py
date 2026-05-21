from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models.schemas import InsightsResponse
from app.services.clustering import compute_insights

router = APIRouter()


@router.get("/insights", response_model=InsightsResponse)
async def get_insights(
    project_id: str,
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> InsightsResponse:
    return InsightsResponse.model_validate(await compute_insights(session, project_id))
