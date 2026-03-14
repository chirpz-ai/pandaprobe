"""Unit tests for evaluation monitor domain logic (no DB or network calls)."""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from app.core.evals.cadence import compute_next_run, validate_cadence
from app.core.evals.entities import EvalMonitor
from app.registry.constants import MonitorCadence, MonitorStatus


# ---------------------------------------------------------------------------
# validate_cadence
# ---------------------------------------------------------------------------


def test_validate_cadence_predefined_every_6h():
    assert validate_cadence("every_6h") == "every_6h"


def test_validate_cadence_predefined_daily():
    assert validate_cadence("daily") == "daily"


def test_validate_cadence_predefined_weekly():
    assert validate_cadence("weekly") == "weekly"


def test_validate_cadence_cron_valid():
    result = validate_cadence("cron:0 9 * * 1-5")
    assert result == "cron:0 9 * * 1-5"


def test_validate_cadence_cron_with_whitespace():
    result = validate_cadence("cron: 0 */6 * * *")
    assert result == "cron:0 */6 * * *"


def test_validate_cadence_invalid_string():
    with pytest.raises(ValueError, match="Invalid cadence"):
        validate_cadence("biweekly")


def test_validate_cadence_invalid_cron():
    with pytest.raises(ValueError, match="Invalid cron expression"):
        validate_cadence("cron:not a cron")


def test_validate_cadence_empty_cron():
    with pytest.raises(ValueError, match="must not be empty"):
        validate_cadence("cron:")


# ---------------------------------------------------------------------------
# compute_next_run
# ---------------------------------------------------------------------------


def test_compute_next_run_every_6h():
    base = datetime(2026, 3, 1, 12, 0, tzinfo=timezone.utc)
    result = compute_next_run("every_6h", base)
    assert result == base + timedelta(hours=6)


def test_compute_next_run_daily():
    base = datetime(2026, 3, 1, 12, 0, tzinfo=timezone.utc)
    result = compute_next_run("daily", base)
    assert result == base + timedelta(days=1)


def test_compute_next_run_weekly():
    base = datetime(2026, 3, 1, 12, 0, tzinfo=timezone.utc)
    result = compute_next_run("weekly", base)
    assert result == base + timedelta(weeks=1)


def test_compute_next_run_cron():
    base = datetime(2026, 3, 1, 8, 30, tzinfo=timezone.utc)
    result = compute_next_run("cron:0 9 * * *", base)
    assert result.hour == 9
    assert result.minute == 0
    assert result >= base


def test_compute_next_run_invalid_cadence():
    base = datetime(2026, 3, 1, 12, 0, tzinfo=timezone.utc)
    with pytest.raises(ValueError, match="Cannot compute"):
        compute_next_run("nope", base)


# ---------------------------------------------------------------------------
# EvalMonitor entity
# ---------------------------------------------------------------------------


def test_eval_monitor_entity_creation():
    now = datetime.now(timezone.utc)
    monitor = EvalMonitor(
        id=uuid4(),
        project_id=uuid4(),
        name="Daily trace eval",
        target_type="TRACE",
        metric_names=["task_completion"],
        filters={},
        sampling_rate=1.0,
        cadence="daily",
        only_if_changed=True,
        status=MonitorStatus.ACTIVE,
        created_at=now,
        updated_at=now,
    )
    assert monitor.target_type == "TRACE"
    assert monitor.status == MonitorStatus.ACTIVE
    assert monitor.next_run_at is None


def test_eval_monitor_entity_with_all_fields():
    now = datetime.now(timezone.utc)
    run_id = uuid4()
    monitor = EvalMonitor(
        id=uuid4(),
        project_id=uuid4(),
        name="Cron session eval",
        target_type="SESSION",
        metric_names=["agent_reliability", "agent_consistency"],
        filters={"user_id": "u1", "signal_weights": {"confidence": 0.5}},
        sampling_rate=0.5,
        model="openai/gpt-4o",
        cadence="cron:0 */12 * * *",
        only_if_changed=False,
        status=MonitorStatus.PAUSED,
        last_run_at=now,
        last_run_id=run_id,
        next_run_at=now + timedelta(hours=12),
        created_at=now,
        updated_at=now,
    )
    assert monitor.target_type == "SESSION"
    assert monitor.model == "openai/gpt-4o"
    assert monitor.last_run_id == run_id
    assert monitor.sampling_rate == 0.5


# ---------------------------------------------------------------------------
# MonitorStatus / MonitorCadence enums
# ---------------------------------------------------------------------------


def test_monitor_status_values():
    assert MonitorStatus.ACTIVE == "ACTIVE"
    assert MonitorStatus.PAUSED == "PAUSED"
    assert len(MonitorStatus) == 2


def test_monitor_cadence_values():
    assert MonitorCadence.EVERY_6H == "every_6h"
    assert MonitorCadence.DAILY == "daily"
    assert MonitorCadence.WEEKLY == "weekly"
    assert MonitorCadence.CUSTOM == "custom"
    assert len(MonitorCadence) == 4
