"""Domain entities for the Evaluation bounded context.

An ``EvalRun`` is a batch job that applies one or more metrics to a
filtered set of traces.  Each metric + trace pair produces a
``TraceScore`` row in the database.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.registry.constants import EvaluationStatus, ScoreDataType, ScoreSource, ScoreStatus


class TraceScore(BaseModel):
    """A single score for a single trace."""

    id: UUID
    trace_id: UUID
    project_id: UUID
    name: str
    data_type: ScoreDataType = ScoreDataType.NUMERIC
    value: str | None
    source: ScoreSource
    status: ScoreStatus = ScoreStatus.SUCCESS
    eval_run_id: UUID | None = None
    author_user_id: str | None = None
    reason: str | None = None
    environment: str | None = None
    config_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime

    @field_validator("value")
    @classmethod
    def _validate_value(cls, v: str | None, info: Any) -> str | None:
        if v is None:
            return v
        data_type = info.data.get("data_type", ScoreDataType.NUMERIC)
        if data_type == ScoreDataType.NUMERIC:
            score = float(v)
            if not (0.0 <= score <= 1.0):
                raise ValueError("NUMERIC score must be in [0.0, 1.0]")
        elif data_type == ScoreDataType.BOOLEAN:
            if v.lower() not in ("true", "false"):
                raise ValueError("BOOLEAN score must be 'true' or 'false'")
        return v


class EvalRun(BaseModel):
    """A batch evaluation job targeting a filtered set of traces.

    Created with status PENDING, transitions to RUNNING while the
    Celery worker processes it, and ends at COMPLETED or FAILED.
    """

    id: UUID
    project_id: UUID
    name: str | None = None
    target_type: str = "TRACE"
    metric_names: list[str]
    filters: dict[str, Any] = Field(default_factory=dict)
    sampling_rate: float = Field(default=1.0, ge=0.0, le=1.0)
    model: str | None = None
    status: EvaluationStatus = EvaluationStatus.PENDING
    total_traces: int = 0
    evaluated_count: int = 0
    failed_count: int = 0
    error_message: str | None = None
    created_at: datetime
    completed_at: datetime | None = None
