from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models.schemas import ReportResponse
from app.services.clustering import latest_cluster_run
from app.services.reports import render_current_topic_report

router = APIRouter()


@router.get("/reports/current", response_model=ReportResponse)
async def get_current_report(
    project_id: str,
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> ReportResponse:
    run = await latest_cluster_run(session, project_id)
    return ReportResponse(
        project_id=project_id,
        latest_cluster_run_id=str(run.id) if run is not None else None,
        report_text=await render_current_topic_report(session, project_id),
    )
