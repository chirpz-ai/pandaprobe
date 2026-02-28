"""Domain entities for the Evaluation bounded context.

An ``Evaluation`` is a job that runs one or more metrics against a
stored trace.  Each metric produces an ``EvaluationResult`` with a
numeric score and optional reasoning from the LLM judge.
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.registry.constants import EvaluationStatus


class EvaluationResult(BaseModel):
    """Outcome of a single metric applied to a trace."""

    id: UUID
    evaluation_id: UUID
    metric_name: str
    score: float = Field(ge=0.0, le=1.0)
    threshold: float = Field(ge=0.0, le=1.0)
    success: bool
    reason: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    evaluated_at: datetime


class Evaluation(BaseModel):
    """A batch-evaluation job targeting one trace with N metrics.

    Created with status PENDING, transitions to RUNNING while the
    Celery worker processes it, and ends at COMPLETED or FAILED.
    """

    id: UUID
    trace_id: UUID
    project_id: UUID
    metric_names: list[str]
    status: EvaluationStatus = EvaluationStatus.PENDING
    results: list[EvaluationResult] = Field(default_factory=list)
    created_at: datetime
    completed_at: datetime | None = None
