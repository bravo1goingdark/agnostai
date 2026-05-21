from arq.connections import RedisSettings

from app.config import get_settings
from app.logging import configure_logging
from app.workers.jobs import process_conversation

settings = get_settings()
configure_logging(settings.log_level)


class WorkerSettings:
    functions = [process_conversation]
    redis_settings = RedisSettings(
        host=settings.redis_host,
        port=settings.redis_port,
        database=settings.redis_database,
        password=settings.redis_password,
    )
    job_timeout = settings.worker_job_timeout_seconds
    max_jobs = 10
