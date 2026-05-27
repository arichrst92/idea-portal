"""Application settings loaded from environment via pydantic-settings."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Centralized settings. Read from .env + OS environment."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_name: str = "IDEA Portal API"
    app_env: str = Field(default="development", pattern="^(development|staging|production)$")
    debug: bool = True
    log_level: str = "INFO"

    # Database
    database_url: str = "postgresql+asyncpg://idea:idea_dev_pass@localhost:5432/idea_portal"
    database_url_sync: str = "postgresql+psycopg://idea:idea_dev_pass@localhost:5432/idea_portal"

    # Redis
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"

    # MinIO
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "minio_admin"
    minio_secret_key: str = "minio_dev_pass"
    minio_bucket: str = "idea-portal"
    minio_use_ssl: bool = False

    # Auth
    secret_key: str = "changeme-in-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    refresh_token_expire_days: int = 7

    # CORS
    cors_origins: str = "http://localhost:5173,http://localhost:3000"

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    # AI
    anthropic_api_key: str = ""
    claude_model: str = "claude-sonnet-4-20250514"


@lru_cache
def get_settings() -> Settings:
    """Cached settings singleton."""
    return Settings()
