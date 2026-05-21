from functools import lru_cache
from typing import Literal
from urllib.parse import urlparse

from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "Agnost Conversation Intelligence"
    app_env: Literal["local", "test", "staging", "production"] = "local"
    log_level: str = "INFO"
    api_key_header: str = "X-API-Key"

    database_url: str = Field(
        default="postgresql+asyncpg://agnost:agnost@postgres:5432/agnost"
    )
    redis_url: str = Field(default="redis://redis:6379/0")

    embedding_model_name: str = "sentence-transformers/all-MiniLM-L6-v2"
    embedding_dimension: int = 384
    worker_job_timeout_seconds: int = 600
    clustering_min_cluster_size: int = 5

    @computed_field  # type: ignore[prop-decorator]
    @property
    def is_local(self) -> bool:
        return self.app_env in {"local", "test"}

    @computed_field  # type: ignore[prop-decorator]
    @property
    def redis_host(self) -> str:
        parsed = urlparse(str(self.redis_url))
        return parsed.hostname or "redis"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def redis_port(self) -> int:
        parsed = urlparse(str(self.redis_url))
        return parsed.port or 6379

    @computed_field  # type: ignore[prop-decorator]
    @property
    def redis_database(self) -> int:
        parsed = urlparse(str(self.redis_url))
        path = parsed.path.lstrip("/")
        return int(path or "0")

    @computed_field  # type: ignore[prop-decorator]
    @property
    def redis_password(self) -> str | None:
        parsed = urlparse(str(self.redis_url))
        return parsed.password


@lru_cache
def get_settings() -> Settings:
    return Settings()
