"""Cadence utilities for evaluation monitors.

Handles parsing and computing next-run times for predefined intervals
(every_6h, daily, weekly) and arbitrary cron expressions (cron:...).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from croniter import croniter

from app.registry.constants import MonitorCadence

_PREDEFINED_DELTAS: dict[str, timedelta] = {
    MonitorCadence.EVERY_6H: timedelta(hours=6),
    MonitorCadence.DAILY: timedelta(days=1),
    MonitorCadence.WEEKLY: timedelta(weeks=1),
}

_CRON_PREFIX = "cron:"


def validate_cadence(cadence: str) -> str:
    """Validate a cadence string and return it normalized.

    Accepted formats:
    - Predefined: "every_6h", "daily", "weekly"
    - Custom cron: "cron:<5-part expression>"

    Raises ``ValueError`` for unrecognized or malformed cadences.
    """
    if cadence in _PREDEFINED_DELTAS:
        return cadence

    if cadence.startswith(_CRON_PREFIX):
        expr = cadence[len(_CRON_PREFIX) :].strip()
        if not expr:
            raise ValueError("Cron expression must not be empty after 'cron:' prefix.")
        if not croniter.is_valid(expr):
            raise ValueError(f"Invalid cron expression: {expr!r}")
        return f"{_CRON_PREFIX}{expr}"

    raise ValueError(
        f"Invalid cadence {cadence!r}. "
        f"Must be one of {list(_PREDEFINED_DELTAS)} or 'cron:<expression>'."
    )


def compute_next_run(cadence: str, from_time: datetime) -> datetime:
    """Compute the next run time from *from_time* given a cadence string.

    For predefined intervals the result is simply ``from_time + delta``.
    For cron expressions the next matching instant after *from_time* is used.
    """
    if cadence in _PREDEFINED_DELTAS:
        return from_time + _PREDEFINED_DELTAS[cadence]

    if cadence.startswith(_CRON_PREFIX):
        expr = cadence[len(_CRON_PREFIX) :].strip()
        base = from_time.astimezone(timezone.utc) if from_time.tzinfo else from_time
        cron = croniter(expr, base)
        return cron.get_next(datetime).replace(tzinfo=timezone.utc)

    raise ValueError(f"Cannot compute next run for cadence {cadence!r}")
