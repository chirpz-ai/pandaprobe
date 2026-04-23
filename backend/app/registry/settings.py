"""Application settings loaded from environment variables.

Uses pydantic-settings to provide typed, validated configuration
with sensible defaults for local development.  Environment-specific
overrides (LOG_LEVEL, LOG_FORMAT, DEBUG) are applied automatically
unless the corresponding variable is explicitly set in the environment.
"""

import os
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import computed_field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Environment(str, Enum):
    """Supported runtime environments."""

    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    TEST = "test"


class Settings(BaseSettings):
    """Central configuration for the PandaProbe service.

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
    PROJECT_NAME: str = "PandaProbe"
    VERSION: str = "0.1.0"
    DESCRIPTION: str = "Open-source agent engineering service"
    DEBUG: bool = False
    ALLOWED_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://localhost:8000",
    ]

    @field_validator("ALLOWED_ORIGINS", mode="before")
    @classmethod
    def _parse_origins(cls, v: object) -> list[str]:
        """Normalize origins. Env vars must use JSON array format: '["http://..."]'."""
        if isinstance(v, str):
            return [s.strip() for s in v.split(",") if s.strip()]
        return v  # type: ignore[return-value]

    # -- PostgreSQL -----------------------------------------------------------
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "pandaprobe_db"
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_POOL_SIZE: int = 5
    POSTGRES_MAX_OVERFLOW: int = 5

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

    # -- LLM Provider Credentials --------------------------------------------
    # Only set the keys for providers you intend to use.  The service
    # gracefully skips providers whose credentials are absent.
    OPENAI_API_KEY: str = ""
    ANTHROPIC_API_KEY: str = ""
    GEMINI_API_KEY: str = ""
    GOOGLE_CLOUD_PROJECT: str = ""
    VERTEX_AI_LOCATION: str = "global"

    # -- Evaluation LLM defaults ---------------------------------------------
    # Model string follows LiteLLM format: "<provider>/<model>"
    # e.g. "openai/gpt-4o-mini", "anthropic/claude-3-5-sonnet-20241022",
    # "vertex_ai/gemini-3.1-flash-lite-preview"
    EVAL_LLM_MODEL: str = "vertex_ai/gemini-3.1-flash-lite-preview"
    EVAL_LLM_TEMPERATURE: float = 1.0
    EVAL_EMBEDDING_MODEL: str = "vertex_ai/text-embedding-004"
    EVAL_EMBEDDING_CACHE_SIZE: int = 2048

    # -- Authentication -------------------------------------------------------
    # "supabase" = Supabase Auth (cloud-hosted, uses SUPABASE_URL + anon key)
    # "firebase" = Firebase Admin SDK (uses GOOGLE_CLOUD_PROJECT + ADC)
    AUTH_PROVIDER: str = "supabase"
    AUTH_ENABLED: bool = True
    SUPABASE_URL: str = ""
    SUPABASE_KEY: str = ""

    # -- Stripe / Billing -----------------------------------------------------
    STRIPE_SECRET_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""
    STRIPE_PRO_PRICE_ID: str = ""
    STRIPE_STARTUP_PRICE_ID: str = ""

    # -- Email / Resend -------------------------------------------------------
    RESEND_API_KEY: str = ""
    RESEND_FROM: str = ""
    RESEND_REPLY_TO: str = ""

    # -- CRM / Attio ----------------------------------------------------------
    ATTIO_API_KEY: str = ""
    ATTIO_LIST_ID: str = ""

    # -- Rate limiting --------------------------------------------------------
    RATE_LIMIT_DEFAULT: str = "200/minute"

    # -- Environment-aware defaults -------------------------------------------

    def model_post_init(self, __context: Any) -> None:
        """Apply environment-specific defaults after model initialization."""
        self._apply_environment_settings()

    def _apply_environment_settings(self) -> None:
        """Override settings per environment when the env var is not explicitly set."""
        _ENV_DEFAULTS: dict[Environment, dict[str, object]] = {
            Environment.DEVELOPMENT: {
                "DEBUG": True,
                "LOG_LEVEL": "DEBUG",
                "LOG_FORMAT": "console",
            },
            Environment.STAGING: {
                "DEBUG": False,
                "LOG_LEVEL": "INFO",
                "LOG_FORMAT": "json",
            },
            Environment.PRODUCTION: {
                "DEBUG": False,
                "LOG_LEVEL": "WARNING",
                "LOG_FORMAT": "json",
            },
            Environment.TEST: {
                "DEBUG": True,
                "LOG_LEVEL": "DEBUG",
                "LOG_FORMAT": "console",
            },
        }

        for key, value in _ENV_DEFAULTS.get(self.APP_ENV, {}).items():
            if key not in os.environ:
                object.__setattr__(self, key, value)

        if not self.AUTH_ENABLED and self.APP_ENV != Environment.DEVELOPMENT:
            import structlog

            structlog.get_logger().warning(
                "auth_enabled_override",
                message="AUTH_ENABLED=false is only allowed in development. Forcing AUTH_ENABLED=true.",
                app_env=self.APP_ENV.value,
            )
            object.__setattr__(self, "AUTH_ENABLED", True)


settings = Settings()
