"""Shared utilities for framework integrations."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def parse_timestamp(value: Any) -> datetime:
    """Best-effort timestamp parsing; falls back to ``datetime.now(utc)``.

    Handles ISO-8601 strings, ``datetime`` objects, and epoch floats.
    """
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, tz=timezone.utc)
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            pass
    return datetime.now(timezone.utc)


def safe_get(data: dict[str, Any], *keys: str, default: Any = None) -> Any:
    """Safely drill into nested dicts: ``safe_get(d, 'a', 'b')`` == ``d['a']['b']``."""
    current = data
    for key in keys:
        if isinstance(current, dict):
            current = current.get(key, default)
        else:
            return default
    return current
