"""Structured logging configuration using structlog.

Provides environment-aware formatters: pretty console output for
development, JSON lines for production.  A JSONL file handler writes
every log entry to a daily rotating file under ``LOG_DIR``.
"""

import json
import logging
import sys
from contextvars import ContextVar
from datetime import datetime
from pathlib import Path
from typing import Any

import structlog

from app.registry.settings import Environment, settings

# Ensure log directory exists.
settings.LOG_DIR.mkdir(parents=True, exist_ok=True)

# Per-request context (org_id, trace_id, etc.) attached to every log line.
_request_context: ContextVar[dict[str, Any] | None] = ContextVar("request_context", default=None)


def bind_context(**kwargs: Any) -> None:
    """Bind key-value pairs to the current request's logging context."""
    current = _request_context.get() or {}
    _request_context.set({**current, **kwargs})


def clear_context() -> None:
    """Reset the per-request logging context."""
    _request_context.set(None)


def _inject_context(_logger: Any, _method: str, event_dict: dict[str, Any]) -> dict[str, Any]:
    """Structlog processor that merges request context into the event dict."""
    ctx = _request_context.get()
    if ctx:
        event_dict.update(ctx)
    return event_dict


# ---------------------------------------------------------------------------
# JSONL file handler
# ---------------------------------------------------------------------------

class _JsonlFileHandler(logging.Handler):
    """Writes structured JSON-lines to a daily log file."""

    def __init__(self, directory: Path) -> None:
        super().__init__()
        self._dir = directory

    def _path(self) -> Path:
        env = settings.APP_ENV.value
        return self._dir / f"{env}-{datetime.now().strftime('%Y-%m-%d')}.jsonl"

    def emit(self, record: logging.LogRecord) -> None:
        """Serialise *record* as JSON and append to the log file."""
        try:
            entry = {
                "timestamp": datetime.fromtimestamp(record.created).isoformat(),
                "level": record.levelname,
                "message": record.getMessage(),
                "module": record.module,
                "environment": settings.APP_ENV.value,
            }
            with open(self._path(), "a", encoding="utf-8") as fh:
                fh.write(json.dumps(entry) + "\n")
        except Exception:
            self.handleError(record)


# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------

def _setup() -> None:
    """Configure structlog + stdlib logging once at import time."""
    log_level = logging.DEBUG if settings.DEBUG else getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)

    file_handler = _JsonlFileHandler(settings.LOG_DIR)
    file_handler.setLevel(log_level)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)

    logging.basicConfig(format="%(message)s", level=log_level, handlers=[file_handler, console_handler])

    shared_processors: list[Any] = [
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        _inject_context,
    ]

    if settings.APP_ENV in {Environment.DEVELOPMENT, Environment.TEST}:
        shared_processors.append(
            structlog.processors.CallsiteParameterAdder(
                {
                    structlog.processors.CallsiteParameter.FILENAME,
                    structlog.processors.CallsiteParameter.FUNC_NAME,
                    structlog.processors.CallsiteParameter.LINENO,
                }
            )
        )

    renderer: Any = (
        structlog.dev.ConsoleRenderer()
        if settings.LOG_FORMAT == "console"
        else structlog.processors.JSONRenderer()
    )

    structlog.configure(
        processors=[*shared_processors, renderer],
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


_setup()

logger: structlog.stdlib.BoundLogger = structlog.get_logger()
