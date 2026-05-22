from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models.schemas import DemoBootstrapRequest, DemoBootstrapResponse
from app.services.clustering import (
    compute_insights,
    latest_cluster_run,
    load_topics,
    run_cluster_batch,
    topic_to_summary,
)
from app.services.reports import write_current_topic_report
from app.services.sample_data import seed_sample_conversations

router = APIRouter()


@router.post("/demo/bootstrap", response_model=DemoBootstrapResponse)
async def bootstrap_demo(
    payload: DemoBootstrapRequest,
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> DemoBootstrapResponse:
    seed_result = await seed_sample_conversations(session, payload.project_id)
    cluster_result = await run_cluster_batch(session, payload.project_id)
    insights = await compute_insights(session, payload.project_id)
    report_path = await write_current_topic_report(session, payload.project_id)
    run = await latest_cluster_run(session, payload.project_id)
    topics = await load_topics(
        session,
        payload.project_id,
        run.id if run is not None else None,
    )
    return DemoBootstrapResponse(
        project_id=payload.project_id,
        accepted=seed_result.accepted,
        duplicate=seed_result.duplicate,
        processed=seed_result.processed,
        topic_count=len(cluster_result.topics),
        latest_cluster_run_id=str(run.id) if run is not None else None,
        report_path=str(report_path),
        report_text=report_path.read_text(encoding="utf-8"),
        insights=insights,
        topics=[topic_to_summary(topic) for topic in topics],
    )
