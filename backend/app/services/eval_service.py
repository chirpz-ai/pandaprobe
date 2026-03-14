"""Service layer for evaluation runs and trace scores."""

from __future__ import annotations

import random
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.evals.cadence import compute_next_run, validate_cadence
from app.core.evals.entities import EvalMonitor, EvalRun, SessionScore, TraceScore, validate_score_value
from app.core.evals.metrics import list_metrics, list_session_metrics
from app.infrastructure.db.models import TraceModel
from app.infrastructure.db.repositories.eval_repo import EvalRepository
from app.infrastructure.db.repositories.trace_repo import TraceRepository
from app.logging import logger
from app.registry.constants import (
    AnalyticsGranularity,
    EvaluationStatus,
    MonitorStatus,
    ScoreDataType,
    ScoreSource,
    ScoreStatus,
    TraceStatus,
)
from app.registry.exceptions import NotFoundError, ValidationError
from app.registry.settings import settings


_SENTINEL = object()


def _resolve_model(model: str | None) -> str:
    """Return the explicit model or resolve the configured default."""
    from app.infrastructure.llm.providers import resolve_model_string

    return resolve_model_string(model or settings.EVAL_LLM_MODEL)


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
            sample_count = int(len(trace_ids) * sampling_rate)
            if sampling_rate > 0:
                sample_count = max(1, sample_count)
            trace_ids = random.sample(trace_ids, sample_count) if sample_count > 0 else []

        resolved_model = _resolve_model(model)

        now = datetime.now(timezone.utc)
        run = EvalRun(
            id=uuid4(),
            project_id=project_id,
            name=name,
            target_type=target_type,
            metric_names=metric_names,
            filters=filters,
            sampling_rate=sampling_rate,
            model=resolved_model,
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
        resolved_model = _resolve_model(model)

        now = datetime.now(timezone.utc)
        run = EvalRun(
            id=uuid4(),
            project_id=project_id,
            name=name,
            target_type="TRACE",
            metric_names=metric_names,
            filters={"trace_ids": [str(tid) for tid in unique_ids]},
            sampling_rate=1.0,
            model=resolved_model,
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
        target_type: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[EvalRun], int]:
        """Paginated listing of eval runs."""
        return await self._repo.list_eval_runs(
            project_id, status=status, target_type=target_type, limit=limit, offset=offset
        )

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

        logger.info(
            "retry_eval_run_created", run_id=str(run.id), original_run_id=str(run_id), total_traces=len(trace_ids)
        )
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
            if run.target_type == "SESSION":
                await self._repo.delete_session_scores_for_run(run_id, project_id)
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

        if value is not None:
            try:
                validate_score_value(value, existing.data_type)
            except ValueError as e:
                raise ValidationError(str(e))

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

    # -- Session eval run creation ---------------------------------------------

    async def create_session_eval_run(
        self,
        project_id: UUID,
        metric_names: list[str],
        *,
        filters: dict[str, Any] | None = None,
        sampling_rate: float = 1.0,
        model: str | None = None,
        name: str | None = None,
        signal_weights: dict[str, float] | None = None,
    ) -> EvalRun:
        """Create a session eval run using filter-based session resolution."""
        available = list_session_metrics()
        invalid = [m for m in metric_names if m not in available]
        if invalid:
            raise ValidationError(f"Unknown session metrics: {', '.join(invalid)}")
        if not metric_names:
            raise ValidationError("At least one metric is required.")

        filters = filters or {}
        session_ids = await self._resolve_session_ids(project_id, filters)
        if not session_ids:
            raise ValidationError("No sessions match the provided filters.")

        if sampling_rate < 1.0:
            sample_count = int(len(session_ids) * sampling_rate)
            if sampling_rate > 0:
                sample_count = max(1, sample_count)
            session_ids = random.sample(session_ids, sample_count) if sample_count > 0 else []

        resolved_model = _resolve_model(model)
        run_filters = {**filters}
        if signal_weights:
            run_filters["signal_weights"] = signal_weights

        now = datetime.now(timezone.utc)
        run = EvalRun(
            id=uuid4(),
            project_id=project_id,
            name=name,
            target_type="SESSION",
            metric_names=metric_names,
            filters=run_filters,
            sampling_rate=sampling_rate,
            model=resolved_model,
            status=EvaluationStatus.PENDING,
            total_traces=len(session_ids),
            evaluated_count=0,
            created_at=now,
        )

        await self._repo.create_eval_run(run)
        await self._session.commit()

        from app.infrastructure.queue.tasks import execute_session_eval_run

        execute_session_eval_run.delay(str(run.id), str(project_id), session_ids)

        logger.info("session_eval_run_created", run_id=str(run.id), total_sessions=len(session_ids))
        return run

    async def create_batch_session_eval_run(
        self,
        project_id: UUID,
        session_ids: list[str],
        metric_names: list[str],
        *,
        model: str | None = None,
        name: str | None = None,
        signal_weights: dict[str, float] | None = None,
    ) -> EvalRun:
        """Create a session eval run for an explicit list of session IDs."""
        available = list_session_metrics()
        invalid = [m for m in metric_names if m not in available]
        if invalid:
            raise ValidationError(f"Unknown session metrics: {', '.join(invalid)}")
        if not metric_names:
            raise ValidationError("At least one metric is required.")
        if not session_ids:
            raise ValidationError("At least one session ID is required.")

        unique_ids = list(dict.fromkeys(session_ids))
        resolved_model = _resolve_model(model)

        run_filters: dict[str, Any] = {"session_ids": unique_ids}
        if signal_weights:
            run_filters["signal_weights"] = signal_weights

        now = datetime.now(timezone.utc)
        run = EvalRun(
            id=uuid4(),
            project_id=project_id,
            name=name,
            target_type="SESSION",
            metric_names=metric_names,
            filters=run_filters,
            sampling_rate=1.0,
            model=resolved_model,
            status=EvaluationStatus.PENDING,
            total_traces=len(unique_ids),
            evaluated_count=0,
            created_at=now,
        )

        await self._repo.create_eval_run(run)
        await self._session.commit()

        from app.infrastructure.queue.tasks import execute_session_eval_run

        execute_session_eval_run.delay(str(run.id), str(project_id), unique_ids)

        logger.info("batch_session_eval_run_created", run_id=str(run.id), total_sessions=len(unique_ids))
        return run

    async def retry_failed_session_run(self, run_id: UUID, project_id: UUID) -> EvalRun:
        """Create a new session run retrying only the sessions with failed scores."""
        original = await self._repo.get_eval_run(run_id, project_id)
        if original is None:
            raise NotFoundError(f"Eval run {run_id} not found.")

        failed_scores = await self._repo.get_failed_session_scores_for_run(run_id, project_id)
        if not failed_scores:
            raise ValidationError("No failed scores to retry in this run.")

        session_ids = sorted(set(s.session_id for s in failed_scores))
        metric_names = sorted(set(s.name for s in failed_scores))

        signal_weights = (original.filters or {}).get("signal_weights")
        run_filters: dict[str, Any] = {"retry_of": str(run_id), "session_ids": session_ids}
        if signal_weights:
            run_filters["signal_weights"] = signal_weights

        resolved_model = _resolve_model(original.model)

        now = datetime.now(timezone.utc)
        run = EvalRun(
            id=uuid4(),
            project_id=project_id,
            name=f"Retry: {original.name or original.id}",
            target_type="SESSION",
            metric_names=metric_names,
            filters=run_filters,
            sampling_rate=1.0,
            model=resolved_model,
            status=EvaluationStatus.PENDING,
            total_traces=len(session_ids),
            evaluated_count=0,
            created_at=now,
        )

        await self._repo.create_eval_run(run)
        await self._session.commit()

        from app.infrastructure.queue.tasks import execute_session_eval_run

        execute_session_eval_run.delay(str(run.id), str(project_id), session_ids)

        logger.info(
            "retry_session_eval_run_created",
            run_id=str(run.id),
            original_run_id=str(run_id),
            total_sessions=len(session_ids),
        )
        return run

    # -- Session score queries -------------------------------------------------

    async def get_session_scores(self, session_id: str, project_id: UUID) -> list[SessionScore]:  # noqa: D102
        return await self._repo.get_session_scores_for_session(session_id, project_id)

    async def get_session_scores_for_run(self, run_id: UUID, project_id: UUID) -> list[SessionScore]:  # noqa: D102
        return await self._repo.get_session_scores_for_run(run_id, project_id)

    async def list_session_scores(  # noqa: D102
        self,
        project_id: UUID,
        *,
        name: str | None = None,
        session_id: str | None = None,
        source: ScoreSource | None = None,
        status: ScoreStatus | None = None,
        eval_run_id: UUID | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[SessionScore], int]:
        return await self._repo.list_session_scores(
            project_id,
            name=name,
            session_id=session_id,
            source=source,
            status=status,
            eval_run_id=eval_run_id,
            date_from=date_from,
            date_to=date_to,
            limit=limit,
            offset=offset,
        )

    async def delete_session_score(self, score_id: UUID, project_id: UUID) -> None:  # noqa: D102
        await self._repo.delete_session_score(score_id, project_id)
        await self._session.commit()

    # -- Session score analytics -----------------------------------------------

    async def get_session_score_summary(  # noqa: D102
        self,
        project_id: UUID,
        *,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> list[dict[str, Any]]:
        return await self._repo.get_session_score_summary(project_id, date_from=date_from, date_to=date_to)

    async def get_session_score_trend(  # noqa: D102
        self,
        project_id: UUID,
        *,
        metric_name: str,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        granularity: AnalyticsGranularity = AnalyticsGranularity.DAY,
    ) -> list[dict[str, Any]]:
        return await self._repo.get_session_score_trend(
            project_id, metric_name=metric_name, date_from=date_from, date_to=date_to, granularity=granularity
        )

    async def get_session_score_distribution(  # noqa: D102
        self,
        project_id: UUID,
        metric_name: str,
        *,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        buckets: int = 10,
    ) -> list[dict[str, Any]]:
        return await self._repo.get_session_score_distribution(
            project_id, metric_name, date_from=date_from, date_to=date_to, buckets=buckets
        )

    async def get_session_score_history(  # noqa: D102
        self,
        project_id: UUID,
        session_id: str,
        *,
        metric_name: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        return await self._repo.get_session_score_history(project_id, session_id, metric_name=metric_name, limit=limit)

    async def get_session_score_comparison(  # noqa: D102
        self,
        project_id: UUID,
        metric_name: str,
        *,
        sort_order: str = "asc",
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        return await self._repo.get_session_score_comparison(
            project_id, metric_name, sort_order=sort_order, limit=limit, offset=offset
        )

    # -- Monitors --------------------------------------------------------------

    async def create_monitor(
        self,
        project_id: UUID,
        name: str,
        target_type: str,
        metric_names: list[str],
        cadence: str,
        *,
        filters: dict[str, Any] | None = None,
        sampling_rate: float = 1.0,
        model: str | None = None,
        only_if_changed: bool = True,
        signal_weights: dict[str, float] | None = None,
    ) -> EvalMonitor:
        """Create and persist a new evaluation monitor."""
        if target_type not in ("TRACE", "SESSION"):
            raise ValidationError("target_type must be 'TRACE' or 'SESSION'.")

        if target_type == "TRACE":
            available = list_metrics()
            if signal_weights:
                raise ValidationError("signal_weights is only valid for SESSION monitors.")
        else:
            available = list_session_metrics()

        invalid = [m for m in metric_names if m not in available]
        if invalid:
            raise ValidationError(f"Unknown metrics: {', '.join(invalid)}")
        if not metric_names:
            raise ValidationError("At least one metric is required.")

        try:
            cadence = validate_cadence(cadence)
        except ValueError as e:
            raise ValidationError(str(e))

        now = datetime.now(timezone.utc)
        next_run = compute_next_run(cadence, now)

        monitor_filters: dict[str, Any] = dict(filters) if filters else {}
        if signal_weights:
            monitor_filters["signal_weights"] = signal_weights

        monitor = EvalMonitor(
            id=uuid4(),
            project_id=project_id,
            name=name,
            target_type=target_type,
            metric_names=metric_names,
            filters=monitor_filters,
            sampling_rate=sampling_rate,
            model=model,
            cadence=cadence,
            only_if_changed=only_if_changed,
            status=MonitorStatus.ACTIVE,
            next_run_at=next_run,
            created_at=now,
            updated_at=now,
        )

        await self._repo.create_monitor(monitor)
        await self._session.commit()
        logger.info("eval_monitor_created", monitor_id=str(monitor.id), cadence=cadence, target=target_type)
        return monitor

    async def get_monitor(self, monitor_id: UUID, project_id: UUID) -> EvalMonitor:  # noqa: D102
        monitor = await self._repo.get_monitor(monitor_id, project_id)
        if monitor is None:
            raise NotFoundError(f"Eval monitor {monitor_id} not found.")
        return monitor

    async def list_monitors(  # noqa: D102
        self,
        project_id: UUID,
        *,
        status: MonitorStatus | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[EvalMonitor], int]:
        return await self._repo.list_monitors(project_id, status=status, limit=limit, offset=offset)

    async def update_monitor(
        self,
        monitor_id: UUID,
        project_id: UUID,
        **fields: Any,
    ) -> EvalMonitor:
        """Partial update of a monitor. Re-validates changed fields."""
        monitor = await self._repo.get_monitor(monitor_id, project_id)
        if monitor is None:
            raise NotFoundError(f"Eval monitor {monitor_id} not found.")

        if "metrics" in fields and fields["metrics"] is not None:
            target_type = fields.get("target_type") or monitor.target_type
            available = list_metrics() if target_type == "TRACE" else list_session_metrics()
            invalid = [m for m in fields["metrics"] if m not in available]
            if invalid:
                raise ValidationError(f"Unknown metrics: {', '.join(invalid)}")
            fields["metric_names"] = fields.pop("metrics")
        else:
            fields.pop("metrics", None)

        signal_weights = fields.pop("signal_weights", _SENTINEL)
        if signal_weights is not _SENTINEL:
            target_type = monitor.target_type
            if target_type == "TRACE" and signal_weights:
                raise ValidationError("signal_weights is only valid for SESSION monitors.")
            base_filters = dict(fields.get("filters") or {}) if "filters" in fields else dict(monitor.filters or {})
            if signal_weights:
                base_filters["signal_weights"] = signal_weights
            else:
                base_filters.pop("signal_weights", None)
            fields["filters"] = base_filters
        elif "filters" in fields:
            existing_sw = (monitor.filters or {}).get("signal_weights")
            if existing_sw is not None:
                new_filters = dict(fields["filters"] or {})
                new_filters["signal_weights"] = existing_sw
                fields["filters"] = new_filters

        new_cadence = fields.get("cadence")
        if new_cadence is not None:
            try:
                fields["cadence"] = validate_cadence(new_cadence)
            except ValueError as e:
                raise ValidationError(str(e))
            now = datetime.now(timezone.utc)
            fields["next_run_at"] = compute_next_run(fields["cadence"], now)

        await self._repo.update_monitor(monitor_id, project_id, **fields)
        await self._session.commit()
        return await self.get_monitor(monitor_id, project_id)

    async def delete_monitor(self, monitor_id: UUID, project_id: UUID) -> None:  # noqa: D102
        monitor = await self._repo.get_monitor(monitor_id, project_id)
        if monitor is None:
            raise NotFoundError(f"Eval monitor {monitor_id} not found.")
        await self._repo.delete_monitor(monitor_id, project_id)
        await self._session.commit()

    async def pause_monitor(self, monitor_id: UUID, project_id: UUID) -> EvalMonitor:  # noqa: D102
        monitor = await self._repo.get_monitor(monitor_id, project_id)
        if monitor is None:
            raise NotFoundError(f"Eval monitor {monitor_id} not found.")
        if monitor.status == MonitorStatus.PAUSED:
            return monitor
        await self._repo.update_monitor(monitor_id, project_id, status=MonitorStatus.PAUSED, next_run_at=None)
        await self._session.commit()
        return await self.get_monitor(monitor_id, project_id)

    async def resume_monitor(self, monitor_id: UUID, project_id: UUID) -> EvalMonitor:  # noqa: D102
        monitor = await self._repo.get_monitor(monitor_id, project_id)
        if monitor is None:
            raise NotFoundError(f"Eval monitor {monitor_id} not found.")
        if monitor.status == MonitorStatus.ACTIVE:
            return monitor
        now = datetime.now(timezone.utc)
        next_run = compute_next_run(monitor.cadence, now)
        await self._repo.update_monitor(monitor_id, project_id, status=MonitorStatus.ACTIVE, next_run_at=next_run)
        await self._session.commit()
        return await self.get_monitor(monitor_id, project_id)

    async def trigger_monitor(self, monitor_id: UUID, project_id: UUID) -> EvalRun:
        """Force-spawn an eval run immediately regardless of cadence."""
        monitor = await self._repo.get_monitor(monitor_id, project_id)
        if monitor is None:
            raise NotFoundError(f"Eval monitor {monitor_id} not found.")

        run, target_ids = await self._spawn_run_for_monitor(monitor)

        now = datetime.now(timezone.utc)
        next_run = compute_next_run(monitor.cadence, now)
        await self._repo.advance_monitor(monitor_id, last_run_at=now, last_run_id=run.id, next_run_at=next_run)
        await self._session.commit()

        self._dispatch_monitor_run(monitor.target_type, run.id, monitor.project_id, target_ids)
        logger.info("monitor_triggered", monitor_id=str(monitor_id), run_id=str(run.id))
        return run

    async def list_monitor_runs(  # noqa: D102
        self,
        monitor_id: UUID,
        project_id: UUID,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[EvalRun], int]:
        monitor = await self._repo.get_monitor(monitor_id, project_id)
        if monitor is None:
            raise NotFoundError(f"Eval monitor {monitor_id} not found.")
        return await self._repo.list_runs_for_monitor(monitor_id, project_id, limit=limit, offset=offset)

    async def should_skip_monitor(self, monitor: EvalMonitor) -> bool:
        """Check if a monitor can be skipped because no new data arrived."""
        if not monitor.only_if_changed:
            return False
        if monitor.last_run_at is None:
            return False

        t = TraceModel.__table__
        stmt = select(func.count()).where(
            t.c.project_id == monitor.project_id,
            t.c.started_at > monitor.last_run_at,
        )
        if monitor.target_type == "SESSION":
            stmt = stmt.where(t.c.session_id.isnot(None))

        filters = monitor.filters or {}
        if filters.get("date_from"):
            stmt = stmt.where(t.c.started_at >= _parse_dt(filters["date_from"]))
        if filters.get("date_to"):
            stmt = stmt.where(t.c.started_at < _parse_dt(filters["date_to"]))
        if filters.get("user_id"):
            stmt = stmt.where(t.c.user_id == filters["user_id"])
        if filters.get("tags"):
            stmt = stmt.where(t.c.tags.overlap(filters["tags"]))

        result = await self._session.execute(stmt)
        return result.scalar_one() == 0

    async def _spawn_run_for_monitor(self, monitor: EvalMonitor) -> tuple[EvalRun, list[str]]:
        """Create an eval run from a monitor's config. Returns (run, target_ids).

        The caller is responsible for committing the transaction and then
        dispatching the Celery task so the worker can see the committed row.
        """
        now = datetime.now(timezone.utc)
        run_name = f"[Monitor] {monitor.name}"

        if monitor.target_type == "TRACE":
            trace_ids = await self._resolve_trace_ids(monitor.project_id, monitor.filters)
            if not trace_ids:
                raise ValidationError("No traces match the monitor's filters.")

            if monitor.sampling_rate < 1.0:
                sample_count = max(1, int(len(trace_ids) * monitor.sampling_rate))
                trace_ids = random.sample(trace_ids, sample_count)

            resolved_model = _resolve_model(monitor.model)
            run = EvalRun(
                id=uuid4(),
                project_id=monitor.project_id,
                name=run_name,
                target_type="TRACE",
                metric_names=monitor.metric_names,
                filters=monitor.filters,
                sampling_rate=monitor.sampling_rate,
                model=resolved_model,
                monitor_id=monitor.id,
                status=EvaluationStatus.PENDING,
                total_traces=len(trace_ids),
                evaluated_count=0,
                created_at=now,
            )
            await self._repo.create_eval_run(run)
            await self._session.flush()
            return run, [str(t) for t in trace_ids]

        else:
            session_ids = await self._resolve_session_ids(monitor.project_id, monitor.filters)
            if not session_ids:
                raise ValidationError("No sessions match the monitor's filters.")

            if monitor.sampling_rate < 1.0:
                sample_count = max(1, int(len(session_ids) * monitor.sampling_rate))
                session_ids = random.sample(session_ids, sample_count)

            resolved_model = _resolve_model(monitor.model)
            run = EvalRun(
                id=uuid4(),
                project_id=monitor.project_id,
                name=run_name,
                target_type="SESSION",
                metric_names=monitor.metric_names,
                filters=monitor.filters,
                sampling_rate=monitor.sampling_rate,
                model=resolved_model,
                monitor_id=monitor.id,
                status=EvaluationStatus.PENDING,
                total_traces=len(session_ids),
                evaluated_count=0,
                created_at=now,
            )
            await self._repo.create_eval_run(run)
            await self._session.flush()
            return run, session_ids

    @staticmethod
    def _dispatch_monitor_run(target_type: str, run_id: UUID, project_id: UUID, target_ids: list[str]) -> None:
        """Dispatch the Celery task for a monitor-spawned run.

        Must only be called **after** the transaction that created the
        eval run row has been committed.
        """
        if target_type == "TRACE":
            from app.infrastructure.queue.tasks import execute_eval_run

            execute_eval_run.delay(str(run_id), str(project_id), target_ids)
        else:
            from app.infrastructure.queue.tasks import execute_session_eval_run

            execute_session_eval_run.delay(str(run_id), str(project_id), target_ids)

    # -- Private helpers -------------------------------------------------------

    async def _resolve_session_ids(self, project_id: UUID, filters: dict[str, Any]) -> list[str]:
        """Resolve matching session IDs using filter criteria."""
        t = TraceModel.__table__
        stmt = select(t.c.session_id).where(t.c.project_id == project_id, t.c.session_id.isnot(None))

        if filters.get("date_from"):
            stmt = stmt.where(t.c.started_at >= _parse_dt(filters["date_from"]))
        if filters.get("date_to"):
            stmt = stmt.where(t.c.started_at < _parse_dt(filters["date_to"]))
        if filters.get("user_id"):
            stmt = stmt.where(t.c.user_id == filters["user_id"])
        if "has_error" in filters and filters["has_error"] is not None:
            if filters["has_error"]:
                stmt = stmt.where(t.c.status == TraceStatus.ERROR.value)
            else:
                stmt = stmt.where(t.c.status != TraceStatus.ERROR.value)
        if filters.get("tags"):
            stmt = stmt.where(t.c.tags.overlap(filters["tags"]))

        stmt = stmt.group_by(t.c.session_id)

        min_count = filters.get("min_trace_count")
        if min_count:
            stmt = stmt.having(func.count() >= min_count)

        result = await self._session.execute(stmt)
        return [row[0] for row in result.all()]

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
