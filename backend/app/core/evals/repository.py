"""Abstract repository protocol for the evaluation bounded context."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Protocol
from uuid import UUID

from app.core.evals.entities import EvalRun, TraceScore
from app.registry.constants import AnalyticsGranularity, EvaluationStatus, ScoreDataType, ScoreSource


class AbstractEvalRepository(Protocol):
    """Port that any eval persistence adapter must implement."""

    # -- Trace score operations ------------------------------------------------

    async def create_score(self, score: TraceScore) -> TraceScore:
        """Persist a single trace score."""
        ...

    async def batch_create_scores(self, scores: list[TraceScore]) -> list[TraceScore]:
        """Persist multiple trace scores."""
        ...

    async def get_scores_for_trace(self, trace_id: UUID, project_id: UUID) -> list[TraceScore]:
        """Fetch all scores for a trace."""
        ...

    async def get_scores_for_traces(self, trace_ids: list[UUID], project_id: UUID) -> dict[UUID, list[TraceScore]]:
        """Batch-fetch scores for multiple traces."""
        ...

    async def list_scores(
        self,
        project_id: UUID,
        *,
        name: str | None = None,
        trace_id: UUID | None = None,
        source: ScoreSource | None = None,
        data_type: ScoreDataType | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[TraceScore], int]:
        """Paginated listing of trace scores."""
        ...

    async def delete_scores_for_trace(self, trace_id: UUID, project_id: UUID) -> int:
        """Delete all scores for a trace."""
        ...

    # -- Eval run operations ---------------------------------------------------

    async def create_eval_run(self, run: EvalRun) -> EvalRun:
        """Persist a new eval run."""
        ...

    async def get_eval_run(self, run_id: UUID, project_id: UUID) -> EvalRun | None:
        """Fetch an eval run by ID."""
        ...

    async def list_eval_runs(
        self,
        project_id: UUID,
        *,
        status: EvaluationStatus | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[EvalRun], int]:
        """Paginated listing of eval runs."""
        ...

    async def update_run_status(
        self,
        run_id: UUID,
        status: EvaluationStatus,
        error_message: str | None = None,
    ) -> None:
        """Update the status of an eval run."""
        ...

    async def increment_progress(self, run_id: UUID, count: int = 1) -> None:
        """Increment the evaluated count on a run."""
        ...

    async def increment_failed(self, run_id: UUID, count: int = 1) -> None:
        """Increment the failed metric count on a run."""
        ...

    # -- Analytics -------------------------------------------------------------

    async def get_score_summary(
        self,
        project_id: UUID,
        *,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> list[dict[str, Any]]:
        """Aggregated score summary grouped by metric."""
        ...

    async def get_score_distribution(
        self,
        project_id: UUID,
        metric_name: str,
        *,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        buckets: int = 10,
    ) -> list[dict[str, Any]]:
        """Histogram of score values for a metric."""
        ...

    async def get_score_trend(
        self,
        project_id: UUID,
        *,
        metric_name: str,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        granularity: AnalyticsGranularity = AnalyticsGranularity.DAY,
    ) -> list[dict[str, Any]]:
        """Time series of average scores for a metric."""
        ...
