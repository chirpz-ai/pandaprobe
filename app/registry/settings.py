"""Application settings loaded from environment variables.

Uses pydantic-settings to provide typed, validated configuration
with sensible defaults for local development.
"""

from enum import Enum
from pathlib import Path

from pydantic import computed_field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Environment(str, Enum):
    """Supported runtime environments."""

    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    TEST = "test"


class Settings(BaseSettings):
    """Central configuration for the Opentracer service.

    Values are read from environment variables. A `.env.*` file matching
    the current ``APP_ENV`` is loaded automatically when present.
    """

    model_config = SettingsConfigDict(
        env_file=(".env", ".env.development"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # -- Application ----------------------------------------------------------
    APP_ENV: Environment = Environment.DEVELOPMENT
    PROJECT_NAME: str = "Opentracer"
    VERSION: str = "0.1.0"
    DESCRIPTION: str = "Open-source agent tracing and evaluation service"
    DEBUG: bool = False
    API_V1_PREFIX: str = "/v1"
    ALLOWED_ORIGINS: list[str] = ["*"]

    @field_validator("ALLOWED_ORIGINS", mode="before")
    @classmethod
    def _parse_origins(cls, v: object) -> list[str]:
        """Accept both JSON arrays and comma-separated strings."""
        if isinstance(v, str):
            return [s.strip() for s in v.split(",") if s.strip()]
        return v  # type: ignore[return-value]

    # -- PostgreSQL -----------------------------------------------------------
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "opentracer_db"
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_POOL_SIZE: int = 20
    POSTGRES_MAX_OVERFLOW: int = 10

    @computed_field  # type: ignore[prop-decorator]
    @property
    def DATABASE_URL(self) -> str:
        """Async database URL for SQLAlchemy (asyncpg driver)."""
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def DATABASE_URL_SYNC(self) -> str:
        """Sync database URL used by Alembic migrations."""
        return (
            f"postgresql+psycopg2://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    # -- Redis / Celery -------------------------------------------------------
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0

    @computed_field  # type: ignore[prop-decorator]
    @property
    def REDIS_URL(self) -> str:
        """Full Redis connection URL."""
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"

    CELERY_TASK_ALWAYS_EAGER: bool = False

    # -- Logging --------------------------------------------------------------
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "console"
    LOG_DIR: Path = Path("logs")

    # -- Rate limiting --------------------------------------------------------
    RATE_LIMIT_DEFAULT: str = "200/minute"


settings = Settings()
