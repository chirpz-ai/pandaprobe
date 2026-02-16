"""Pure domain entities for evaluation metrics.

These are placeholder definitions for the future evaluation pipeline.
Metric definitions describe *what* to evaluate; ``EvaluationResult``
records capture the outcome of running a metric against a trace.
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class MetricDefinition(BaseModel):
    """Describes a single evaluation metric (e.g. relevancy, hallucination)."""

    id: UUID
    name: str = Field(min_length=1, max_length=255)
    prompt_template: str
    score_range: tuple[float, float] = (0.0, 1.0)


class EvaluationResult(BaseModel):
    """Outcome of applying a metric to a trace or span."""

    id: UUID
    trace_id: UUID
    span_id: UUID | None = None
    metric_id: UUID
    score: float
    reasoning: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    evaluated_at: datetime
