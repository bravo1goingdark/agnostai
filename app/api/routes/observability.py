from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models.tables import ClusterRun, ProcessingJob

router = APIRouter()


@router.get("/observability")
async def get_observability(
    project_id: str,
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> dict[str, object]:
    queued_result = await session.execute(
        select(func.count())
        .select_from(ProcessingJob)
        .where(ProcessingJob.project_id == project_id)
        .where(ProcessingJob.status == "queued")
    )
    queued_jobs = int(queued_result.scalar_one() or 0)

    failed_result = await session.execute(
        select(func.count())
        .select_from(ProcessingJob)
        .where(ProcessingJob.project_id == project_id)
        .where(ProcessingJob.status == "failed")
    )
    failed_jobs = int(failed_result.scalar_one() or 0)

    latest_cluster = await session.execute(
        select(ClusterRun)
        .where(ClusterRun.project_id == project_id)
        .where(ClusterRun.status == "completed")
        .order_by(ClusterRun.created_at.desc())
        .limit(1)
    )
    cluster_run = latest_cluster.scalar_one_or_none()
    cluster_run_duration_ms: int | None = None
    if cluster_run is not None and cluster_run.completed_at is not None:
        cluster_run_duration_ms = int(
            (cluster_run.completed_at - cluster_run.created_at).total_seconds()
            * 1000
        )

    return {
        "project_id": project_id,
        "queue_depth": queued_jobs,
        "failed_job_count": failed_jobs,
        "latest_cluster_run_duration_ms": cluster_run_duration_ms,
    }
