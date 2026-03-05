"""Service layer for evaluation runs and trace scores."""

from __future__ import annotations

import random
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.evals.entities import EvalRun, TraceScore
from app.core.evals.metrics import list_metrics
from app.infrastructure.db.models import TraceModel
from app.infrastructure.db.repositories.eval_repo import EvalRepository
from app.infrastructure.db.repositories.trace_repo import TraceRepository
from app.logging import logger
from app.registry.constants import (
    AnalyticsGranularity,
    EvaluationStatus,
    ScoreDataType,
    ScoreSource,
    ScoreStatus,
    TraceStatus,
)
from app.registry.exceptions import NotFoundError, ValidationError


class EvalService:
    """Orchestrates eval run creation, score retrieval, and analytics."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = EvalRepository(session)

    # -- Eval run creation -----------------------------------------------------

    async def create_eval_run(
        self,
        project_id: UUID,
        metric_names: list[str],
        *,
        filters: dict[str, Any] | None = None,
        sampling_rate: float = 1.0,
        model: str | None = None,
        name: str | None = None,
        target_type: str = "TRACE",
    ) -> EvalRun:
        """Validate metrics, resolve traces, and enqueue an eval run."""
        available = list_metrics()
        invalid = [m for m in metric_names if m not in available]
        if invalid:
            raise ValidationError(f"Unknown metrics: {', '.join(invalid)}")

        if not metric_names:
            raise ValidationError("At least one metric is required.")

        filters = filters or {}

        trace_ids = await self._resolve_trace_ids(project_id, filters)
        if not trace_ids:
            raise ValidationError("No traces match the provided filters.")

        if sampling_rate < 1.0:
            sample_count = max(1, int(len(trace_ids) * sampling_rate))
            trace_ids = random.sample(trace_ids, sample_count)

        now = datetime.now(timezone.utc)
        run = EvalRun(
            id=uuid4(),
            project_id=project_id,
            name=name,
            target_type=target_type,
            metric_names=metric_names,
            filters=filters,
            sampling_rate=sampling_rate,
            model=model,
            status=EvaluationStatus.PENDING,
            total_traces=len(trace_ids),
            evaluated_count=0,
            created_at=now,
        )

        await self._repo.create_eval_run(run)
        await self._session.commit()

        from app.infrastructure.queue.tasks import execute_eval_run

        execute_eval_run.delay(str(run.id), str(project_id), [str(tid) for tid in trace_ids])

        logger.info("eval_run_created", run_id=str(run.id), total_traces=len(trace_ids))
        return run

    async def create_batch_eval_run(
        self,
        project_id: UUID,
        trace_ids: list[UUID],
        metric_names: list[str],
        *,
        model: str | None = None,
        name: str | None = None,
    ) -> EvalRun:
        """Create an eval run for an explicit list of trace IDs."""
        available = list_metrics()
        invalid = [m for m in metric_names if m not in available]
        if invalid:
            raise ValidationError(f"Unknown metrics: {', '.join(invalid)}")
        if not metric_names:
            raise ValidationError("At least one metric is required.")
        if not trace_ids:
            raise ValidationError("At least one trace ID is required.")

        unique_ids = list(dict.fromkeys(trace_ids))

        now = datetime.now(timezone.utc)
        run = EvalRun(
            id=uuid4(),
            project_id=project_id,
            name=name,
            target_type="TRACE",
            metric_names=metric_names,
            filters={"trace_ids": [str(tid) for tid in unique_ids]},
            sampling_rate=1.0,
            model=model,
            status=EvaluationStatus.PENDING,
            total_traces=len(unique_ids),
            evaluated_count=0,
            created_at=now,
        )

        await self._repo.create_eval_run(run)
        await self._session.commit()

        from app.infrastructure.queue.tasks import execute_eval_run

        execute_eval_run.delay(str(run.id), str(project_id), [str(tid) for tid in unique_ids])

        logger.info("batch_eval_run_created", run_id=str(run.id), total_traces=len(unique_ids))
        return run

    # -- Eval run queries ------------------------------------------------------

    async def get_eval_run(self, run_id: UUID, project_id: UUID) -> EvalRun:
        """Fetch an eval run or raise NotFoundError."""
        run = await self._repo.get_eval_run(run_id, project_id)
        if run is None:
            raise NotFoundError(f"Eval run {run_id} not found.")
        return run

    async def list_eval_runs(
        self,
        project_id: UUID,
        *,
        status: EvaluationStatus | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[EvalRun], int]:
        """Paginated listing of eval runs."""
        return await self._repo.list_eval_runs(project_id, status=status, limit=limit, offset=offset)

    async def retry_failed_run(self, run_id: UUID, project_id: UUID) -> EvalRun:
        """Create a new run retrying only the exact failed trace+metric pairs."""
        from collections import defaultdict

        original = await self._repo.get_eval_run(run_id, project_id)
        if original is None:
            raise NotFoundError(f"Eval run {run_id} not found.")

        failed_scores = await self._repo.get_failed_scores_for_run(run_id, project_id)
        if not failed_scores:
            raise ValidationError("No failed scores to retry in this run.")

        trace_metric_map: dict[UUID, list[str]] = defaultdict(list)
        for s in failed_scores:
            if s.name not in trace_metric_map[s.trace_id]:
                trace_metric_map[s.trace_id].append(s.name)

        trace_ids = list(trace_metric_map.keys())
        all_metric_names = sorted({name for names in trace_metric_map.values() for name in names})

        now = datetime.now(timezone.utc)
        run = EvalRun(
            id=uuid4(),
            project_id=project_id,
            name=f"Retry: {original.name or original.id}",
            target_type="TRACE",
            metric_names=all_metric_names,
            filters={"retry_of": str(run_id), "trace_ids": [str(tid) for tid in trace_ids]},
            sampling_rate=1.0,
            model=original.model,
            status=EvaluationStatus.PENDING,
            total_traces=len(trace_ids),
            evaluated_count=0,
            created_at=now,
        )

        await self._repo.create_eval_run(run)
        await self._session.commit()

        from app.infrastructure.queue.tasks import execute_eval_run

        serialized_map = {str(tid): metrics for tid, metrics in trace_metric_map.items()}
        execute_eval_run.delay(
            str(run.id),
            str(project_id),
            [str(tid) for tid in trace_ids],
            trace_metric_map=serialized_map,
        )

        logger.info("retry_eval_run_created", run_id=str(run.id), original_run_id=str(run_id), total_traces=len(trace_ids))
        return run

    async def get_scores_for_run(self, run_id: UUID, project_id: UUID) -> list[TraceScore]:
        """Fetch all scores produced by a specific eval run."""
        return await self._repo.get_scores_for_run(run_id, project_id)

    async def delete_eval_run(self, run_id: UUID, project_id: UUID, *, delete_scores: bool = False) -> None:
        """Delete an eval run, optionally cascading to its scores."""
        run = await self._repo.get_eval_run(run_id, project_id)
        if run is None:
            raise NotFoundError(f"Eval run {run_id} not found.")
        if delete_scores:
            await self._repo.delete_scores_for_run(run_id, project_id)
        await self._repo.delete_eval_run(run_id, project_id)
        await self._session.commit()

    # -- Trace score creation --------------------------------------------------

    async def create_score(
        self,
        project_id: UUID,
        trace_id: UUID,
        name: str,
        value: str,
        *,
        data_type: ScoreDataType = ScoreDataType.NUMERIC,
        source: ScoreSource = ScoreSource.ANNOTATION,
        reason: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> TraceScore:
        """Manually create a trace score (annotation or programmatic)."""
        now = datetime.now(timezone.utc)
        score = TraceScore(
            id=uuid4(),
            trace_id=trace_id,
            project_id=project_id,
            name=name,
            data_type=data_type,
            value=value,
            source=source,
            status=ScoreStatus.SUCCESS,
            reason=reason,
            metadata=metadata or {},
            created_at=now,
            updated_at=now,
        )
        await self._repo.create_score(score)
        await self._session.commit()
        return score

    # -- Trace score queries ---------------------------------------------------

    async def get_scores_for_trace(self, trace_id: UUID, project_id: UUID) -> list[TraceScore]:
        """Fetch all scores for a single trace."""
        return await self._repo.get_scores_for_trace(trace_id, project_id)

    async def get_latest_scores_for_trace(self, trace_id: UUID, project_id: UUID) -> list[TraceScore]:
        """Fetch the latest score per metric for a trace (deduplicated)."""
        return await self._repo.get_latest_scores_for_trace(trace_id, project_id)

    async def update_score(
        self,
        score_id: UUID,
        project_id: UUID,
        *,
        value: str | None = None,
        reason: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> TraceScore:
        """Manually edit a score. Automatically marks as ANNOTATION + SUCCESS."""
        existing = await self._repo.get_score_by_id(score_id, project_id)
        if existing is None:
            raise NotFoundError(f"Trace score {score_id} not found.")

        await self._repo.update_score(
            score_id,
            project_id,
            value=value,
            reason=reason,
            metadata=metadata,
            status=ScoreStatus.SUCCESS,
            source=ScoreSource.ANNOTATION,
        )
        await self._session.commit()

        updated = await self._repo.get_score_by_id(score_id, project_id)
        if updated is None:
            raise NotFoundError(f"Trace score {score_id} not found after update.")
        return updated

    async def delete_score(self, score_id: UUID, project_id: UUID) -> None:
        """Delete a single trace score."""
        existing = await self._repo.get_score_by_id(score_id, project_id)
        if existing is None:
            raise NotFoundError(f"Trace score {score_id} not found.")
        await self._repo.delete_score(score_id, project_id)
        await self._session.commit()

    async def list_scores(
        self,
        project_id: UUID,
        *,
        name: str | None = None,
        trace_id: UUID | None = None,
        source: ScoreSource | None = None,
        status: ScoreStatus | None = None,
        data_type: ScoreDataType | None = None,
        eval_run_id: UUID | None = None,
        environment: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[TraceScore], int]:
        """Paginated listing of trace scores with filters."""
        return await self._repo.list_scores(
            project_id,
            name=name,
            trace_id=trace_id,
            source=source,
            status=status,
            data_type=data_type,
            eval_run_id=eval_run_id,
            environment=environment,
            date_from=date_from,
            date_to=date_to,
            limit=limit,
            offset=offset,
        )

    # -- Analytics -------------------------------------------------------------

    async def get_score_summary(
        self,
        project_id: UUID,
        *,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> list[dict[str, Any]]:
        """Aggregated score summary grouped by metric."""
        return await self._repo.get_score_summary(project_id, date_from=date_from, date_to=date_to)

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
        return await self._repo.get_score_distribution(
            project_id, metric_name, date_from=date_from, date_to=date_to, buckets=buckets
        )

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
        return await self._repo.get_score_trend(
            project_id, metric_name=metric_name, date_from=date_from, date_to=date_to, granularity=granularity
        )

    # -- Private helpers -------------------------------------------------------

    async def _resolve_trace_ids(self, project_id: UUID, filters: dict[str, Any]) -> list[UUID]:
        """Resolve matching trace IDs using the same filter logic as the traces API."""
        t = TraceModel.__table__
        stmt = select(t.c.trace_id).where(t.c.project_id == project_id)

        status_str = filters.get("status")
        status = TraceStatus(status_str) if status_str else None

        stmt = TraceRepository._apply_trace_filters(
            stmt,
            t,
            session_id=filters.get("session_id"),
            status=status,
            user_id=filters.get("user_id"),
            tags=filters.get("tags"),
            name=filters.get("name"),
            started_after=_parse_dt(filters.get("date_from")),
            started_before=_parse_dt(filters.get("date_to")),
        )

        result = await self._session.execute(stmt)
        return [row[0] for row in result.all()]


def _parse_dt(value: Any) -> datetime | None:
    """Parse an ISO-format datetime string, or return None."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value))
