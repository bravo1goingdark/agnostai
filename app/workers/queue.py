from collections.abc import Awaitable, Callable
from datetime import timedelta
from typing import Any, Protocol, runtime_checkable

from arq.connections import RedisSettings, create_pool

from app.config import get_settings


@runtime_checkable
class QueueClient(Protocol):
    async def enqueue_job(
        self,
        function: str,
        *args: Any,
        _job_id: str | None = None,
        _queue_name: str | None = None,
        _defer_until: Any = None,
        _defer_by: int | float | timedelta | None = None,
        _expires: int | float | timedelta | None = None,
        _job_try: int | None = None,
        **kwargs: Any,
    ) -> object:
        ...

    async def aclose(self) -> None: ...


type QueueFactory = Callable[[], Awaitable[QueueClient]]


async def create_queue() -> QueueClient:
    settings = get_settings()
    redis_settings = RedisSettings(
        host=settings.redis_host,
        port=settings.redis_port,
        database=settings.redis_database,
        password=settings.redis_password,
    )
    return await create_pool(redis_settings)


async def enqueue_process_conversation(
    redis: QueueClient,
    project_id: str,
    conversation_id: str,
) -> str | None:
    job = await redis.enqueue_job(
        "process_conversation",
        project_id,
        conversation_id,
    )
    return getattr(job, "job_id", None)


async def enqueue_process_conversation_via_factory(
    factory: QueueFactory,
    project_id: str,
    conversation_id: str,
) -> str | None:
    redis = await factory()
    try:
        return await enqueue_process_conversation(redis, project_id, conversation_id)
    finally:
        await redis.aclose()
