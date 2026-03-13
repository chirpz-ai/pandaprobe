"""PostgreSQL repository for eval runs, trace scores, and session scores."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import Float as SAFloat, cast, delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.evals.entities import EvalMonitor, EvalRun, SessionScore, TraceScore
from app.infrastructure.db.models import EvalMonitorModel, EvalRunModel, SessionScoreModel, TraceScoreModel
from app.registry.constants import (
    AnalyticsGranularity,
    EvaluationStatus,
    MonitorStatus,
    ScoreDataType,
    ScoreSource,
    ScoreStatus,
)


class EvalRepository:
    """Persistence adapter for eval runs, trace scores, and analytics."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # -- Trace score operations ------------------------------------------------

    async def create_score(self, score: TraceScore) -> TraceScore:
        """Persist a single trace score."""
        row = TraceScoreModel(
            id=score.id,
            trace_id=score.trace_id,
            project_id=score.project_id,
            name=score.name,
            data_type=score.data_type,
            value=score.value,
            source=score.source,
            status=score.status,
            eval_run_id=score.eval_run_id,
            author_user_id=score.author_user_id,
            reason=score.reason,
            environment=score.environment,
            config_id=score.config_id,
            metadata_=score.metadata,
            created_at=score.created_at,
            updated_at=score.updated_at,
        )
        self._session.add(row)
        await self._session.flush()
        return score

    async def batch_create_scores(self, scores: list[TraceScore]) -> list[TraceScore]:
        """Persist multiple trace scores in bulk."""
        rows = [
            TraceScoreModel(
                id=s.id,
                trace_id=s.trace_id,
                project_id=s.project_id,
                name=s.name,
                data_type=s.data_type,
                value=s.value,
                source=s.source,
                status=s.status,
                eval_run_id=s.eval_run_id,
                author_user_id=s.author_user_id,
                reason=s.reason,
                environment=s.environment,
                config_id=s.config_id,
                metadata_=s.metadata,
                created_at=s.created_at,
                updated_at=s.updated_at,
            )
            for s in scores
        ]
        self._session.add_all(rows)
        await self._session.flush()
        return scores

    async def get_scores_for_trace(self, trace_id: UUID, project_id: UUID) -> list[TraceScore]:
        """Fetch all scores for a specific trace."""
        stmt = (
            select(TraceScoreModel)
            .where(TraceScoreModel.trace_id == trace_id, TraceScoreModel.project_id == project_id)
            .order_by(TraceScoreModel.created_at.desc())
        )
        result = await self._session.execute(stmt)
        return [self._to_score(row) for row in result.scalars().all()]

    async def get_latest_scores_for_trace(self, trace_id: UUID, project_id: UUID) -> list[TraceScore]:
        """Fetch the latest score per metric name for a trace.

        Returns one row per metric name: the most recently created score,
        regardless of status. If the latest is FAILED, the user sees it
        and can re-run.
        """
        t = TraceScoreModel.__table__
        stmt = (
            select(t)
            .distinct(t.c.name)
            .where(t.c.trace_id == trace_id, t.c.project_id == project_id)
            .order_by(t.c.name, t.c.created_at.desc())
        )
        result = await self._session.execute(stmt)
        return [self._to_score_from_row(r) for r in result.mappings().all()]

    async def get_scores_for_traces(self, trace_ids: list[UUID], project_id: UUID) -> dict[UUID, list[TraceScore]]:
        """Batch-fetch scores for multiple traces."""
        if not trace_ids:
            return {}
        stmt = (
            select(TraceScoreModel)
            .where(TraceScoreModel.trace_id.in_(trace_ids), TraceScoreModel.project_id == project_id)
            .order_by(TraceScoreModel.created_at.desc())
        )
        result = await self._session.execute(stmt)
        grouped: dict[UUID, list[TraceScore]] = defaultdict(list)
        for row in result.scalars().all():
            score = self._to_score(row)
            grouped[score.trace_id].append(score)
        return dict(grouped)

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
        t = TraceScoreModel.__table__
        base = select(t).where(t.c.project_id == project_id)

        if name is not None:
            base = base.where(t.c.name == name)
        if trace_id is not None:
            base = base.where(t.c.trace_id == trace_id)
        if source is not None:
            base = base.where(t.c.source == source.value)
        if status is not None:
            base = base.where(t.c.status == status.value)
        if data_type is not None:
            base = base.where(t.c.data_type == data_type.value)
        if eval_run_id is not None:
            base = base.where(t.c.eval_run_id == eval_run_id)
        if environment is not None:
            base = base.where(t.c.environment == environment)
        if date_from is not None:
            base = base.where(t.c.created_at >= date_from)
        if date_to is not None:
            base = base.where(t.c.created_at < date_to)

        count_stmt = select(func.count()).select_from(base.subquery())
        total = (await self._session.execute(count_stmt)).scalar_one()

        data_stmt = base.order_by(t.c.created_at.desc()).offset(offset).limit(limit)
        result = await self._session.execute(data_stmt)
        scores = [self._to_score_from_row(r) for r in result.mappings().all()]
        return scores, total

    async def delete_scores_for_trace(self, trace_id: UUID, project_id: UUID) -> int:
        """Delete all scores for a trace."""
        stmt = delete(TraceScoreModel).where(
            TraceScoreModel.trace_id == trace_id, TraceScoreModel.project_id == project_id
        )
        result = await self._session.execute(stmt)
        return result.rowcount

    async def get_score_by_id(self, score_id: UUID, project_id: UUID) -> TraceScore | None:
        """Fetch a single score by its ID."""
        stmt = select(TraceScoreModel).where(TraceScoreModel.id == score_id, TraceScoreModel.project_id == project_id)
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return self._to_score(row)

    async def update_score(
        self,
        score_id: UUID,
        project_id: UUID,
        **fields: Any,
    ) -> None:
        """Update editable fields on a score. Sets updated_at automatically."""
        values = {k: v for k, v in fields.items() if v is not None}
        if not values:
            return
        if "metadata" in values:
            values["metadata_"] = values.pop("metadata")
        values["updated_at"] = datetime.now(timezone.utc)
        stmt = (
            update(TraceScoreModel)
            .where(TraceScoreModel.id == score_id, TraceScoreModel.project_id == project_id)
            .values(**values)
        )
        await self._session.execute(stmt)

    # -- Eval run operations ---------------------------------------------------

    async def create_eval_run(self, run: EvalRun) -> EvalRun:
        """Persist a new eval run."""
        row = EvalRunModel(
            id=run.id,
            project_id=run.project_id,
            name=run.name,
            target_type=run.target_type,
            metric_names=run.metric_names,
            filters=run.filters,
            sampling_rate=run.sampling_rate,
            model=run.model,
            monitor_id=run.monitor_id,
            status=run.status,
            total_traces=run.total_traces,
            evaluated_count=run.evaluated_count,
            failed_count=run.failed_count,
            error_message=run.error_message,
            created_at=run.created_at,
            completed_at=run.completed_at,
        )
        self._session.add(row)
        await self._session.flush()
        return run

    async def get_eval_run(self, run_id: UUID, project_id: UUID) -> EvalRun | None:
        """Fetch an eval run by ID."""
        stmt = select(EvalRunModel).where(EvalRunModel.id == run_id, EvalRunModel.project_id == project_id)
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return self._to_eval_run(row)

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
        t = EvalRunModel.__table__
        base = select(t).where(t.c.project_id == project_id)
        if status is not None:
            base = base.where(t.c.status == status.value)
        if target_type is not None:
            base = base.where(t.c.target_type == target_type)

        count_stmt = select(func.count()).select_from(base.subquery())
        total = (await self._session.execute(count_stmt)).scalar_one()

        data_stmt = base.order_by(t.c.created_at.desc()).offset(offset).limit(limit)
        result = await self._session.execute(data_stmt)
        runs = [self._to_eval_run_from_row(r) for r in result.mappings().all()]
        return runs, total

    async def update_run_status(
        self,
        run_id: UUID,
        status: EvaluationStatus,
        error_message: str | None = None,
    ) -> None:
        """Update the status of an eval run.

        Clears ``error_message`` on RUNNING/COMPLETED so a successful
        retry doesn't retain a stale error from a previous attempt.
        """
        values: dict[str, Any] = {"status": status}
        if status == EvaluationStatus.FAILED:
            values["error_message"] = error_message
            values["completed_at"] = datetime.now(timezone.utc)
        elif status == EvaluationStatus.COMPLETED:
            values["error_message"] = None
            values["completed_at"] = datetime.now(timezone.utc)
        elif status == EvaluationStatus.RUNNING:
            values["error_message"] = None
            values["completed_at"] = None
        stmt = update(EvalRunModel).where(EvalRunModel.id == run_id).values(**values)
        await self._session.execute(stmt)

    async def increment_progress(self, run_id: UUID, count: int = 1) -> None:
        """Increment the evaluated count on a run."""
        stmt = (
            update(EvalRunModel)
            .where(EvalRunModel.id == run_id)
            .values(evaluated_count=EvalRunModel.evaluated_count + count)
        )
        await self._session.execute(stmt)

    async def reset_run_counters(self, run_id: UUID) -> None:
        """Reset progress counters to zero (used before a retry)."""
        stmt = update(EvalRunModel).where(EvalRunModel.id == run_id).values(evaluated_count=0, failed_count=0)
        await self._session.execute(stmt)

    async def increment_failed(self, run_id: UUID, count: int = 1) -> None:
        """Increment the failed metric count on a run."""
        stmt = (
            update(EvalRunModel)
            .where(EvalRunModel.id == run_id)
            .values(failed_count=EvalRunModel.failed_count + count)
        )
        await self._session.execute(stmt)

    async def get_failed_scores_for_run(self, run_id: UUID, project_id: UUID) -> list[TraceScore]:
        """Fetch FAILED scores belonging to a specific eval run."""
        stmt = select(TraceScoreModel).where(
            TraceScoreModel.eval_run_id == run_id,
            TraceScoreModel.project_id == project_id,
            TraceScoreModel.status == ScoreStatus.FAILED.value,
        )
        result = await self._session.execute(stmt)
        return [self._to_score(row) for row in result.scalars().all()]

    async def get_scores_for_run(self, run_id: UUID, project_id: UUID) -> list[TraceScore]:
        """Fetch all scores belonging to a specific eval run."""
        stmt = (
            select(TraceScoreModel)
            .where(TraceScoreModel.eval_run_id == run_id, TraceScoreModel.project_id == project_id)
            .order_by(TraceScoreModel.created_at.desc())
        )
        result = await self._session.execute(stmt)
        return [self._to_score(row) for row in result.scalars().all()]

    async def delete_eval_run(self, run_id: UUID, project_id: UUID) -> None:
        """Delete an eval run record."""
        stmt = delete(EvalRunModel).where(EvalRunModel.id == run_id, EvalRunModel.project_id == project_id)
        await self._session.execute(stmt)

    async def delete_scores_for_run(self, run_id: UUID, project_id: UUID) -> int:
        """Delete all scores belonging to a specific eval run."""
        stmt = delete(TraceScoreModel).where(
            TraceScoreModel.eval_run_id == run_id, TraceScoreModel.project_id == project_id
        )
        result = await self._session.execute(stmt)
        return result.rowcount

    async def delete_score(self, score_id: UUID, project_id: UUID) -> None:
        """Delete a single trace score."""
        stmt = delete(TraceScoreModel).where(TraceScoreModel.id == score_id, TraceScoreModel.project_id == project_id)
        await self._session.execute(stmt)

    # -- Analytics -------------------------------------------------------------

    async def get_score_summary(
        self,
        project_id: UUID,
        *,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> list[dict[str, Any]]:
        """Aggregated score summary grouped by metric."""
        t = TraceScoreModel.__table__
        numeric_value = cast(t.c.value, SAFloat)
        is_success = t.c.status == ScoreStatus.SUCCESS.value
        is_numeric_success = (t.c.data_type == ScoreDataType.NUMERIC.value) & is_success

        base = select(
            t.c.name.label("metric_name"),
            func.count().filter(is_success).label("success_count"),
            func.count().filter(t.c.status == ScoreStatus.FAILED.value).label("failed_count"),
            func.avg(numeric_value).filter(is_numeric_success).label("avg_score"),
            func.min(numeric_value).filter(is_numeric_success).label("min_score"),
            func.max(numeric_value).filter(is_numeric_success).label("max_score"),
            func.percentile_cont(0.5).within_group(numeric_value).filter(is_numeric_success).label("median_score"),
            func.max(t.c.created_at).label("latest_score_at"),
        ).where(t.c.project_id == project_id)

        if date_from is not None:
            base = base.where(t.c.created_at >= date_from)
        if date_to is not None:
            base = base.where(t.c.created_at < date_to)

        base = base.group_by(t.c.name)
        result = await self._session.execute(base)
        return [
            {
                "metric_name": row.metric_name,
                "avg_score": float(row.avg_score) if row.avg_score is not None else None,
                "min_score": float(row.min_score) if row.min_score is not None else None,
                "max_score": float(row.max_score) if row.max_score is not None else None,
                "median_score": float(row.median_score) if row.median_score is not None else None,
                "success_count": row.success_count,
                "failed_count": row.failed_count,
                "latest_score_at": row.latest_score_at.isoformat() if row.latest_score_at else None,
            }
            for row in result.all()
        ]

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
        t = TraceScoreModel.__table__
        numeric_value = cast(t.c.value, SAFloat)
        bucket_col = func.width_bucket(numeric_value, 0.0, 1.0, buckets)

        base = select(
            bucket_col.label("bucket"),
            func.count().label("count"),
        ).where(
            t.c.project_id == project_id,
            t.c.name == metric_name,
            t.c.data_type == ScoreDataType.NUMERIC.value,
            t.c.status == ScoreStatus.SUCCESS.value,
        )

        if date_from is not None:
            base = base.where(t.c.created_at >= date_from)
        if date_to is not None:
            base = base.where(t.c.created_at < date_to)

        base = base.group_by(bucket_col).order_by(bucket_col)
        result = await self._session.execute(base)

        step = 1.0 / buckets
        return [
            {
                "bucket": row.bucket,
                "bucket_min": round(max(0.0, (row.bucket - 1) * step), 4),
                "bucket_max": round(min(1.0, row.bucket * step), 4),
                "count": row.count,
            }
            for row in result.all()
        ]

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
        t = TraceScoreModel.__table__
        numeric_value = cast(t.c.value, SAFloat)
        bucket = func.date_trunc(granularity.value, t.c.created_at).label("bucket")

        base = select(
            bucket,
            t.c.name.label("metric_name"),
            func.avg(numeric_value).label("avg_score"),
            func.count().label("count"),
        ).where(
            t.c.project_id == project_id,
            t.c.name == metric_name,
            t.c.data_type == ScoreDataType.NUMERIC.value,
            t.c.status == ScoreStatus.SUCCESS.value,
        )

        if date_from is not None:
            base = base.where(t.c.created_at >= date_from)
        if date_to is not None:
            base = base.where(t.c.created_at < date_to)

        base = base.group_by(bucket, t.c.name).order_by(bucket)
        result = await self._session.execute(base)
        return [
            {
                "bucket": row.bucket.isoformat() if row.bucket else None,
                "metric_name": row.metric_name,
                "avg_score": float(row.avg_score) if row.avg_score is not None else 0.0,
                "count": row.count,
            }
            for row in result.all()
        ]

    # -- Session score operations ----------------------------------------------

    async def create_session_score(self, score: SessionScore) -> SessionScore:
        """Persist a single session score."""
        row = SessionScoreModel(
            id=score.id,
            session_id=score.session_id,
            project_id=score.project_id,
            name=score.name,
            data_type=score.data_type,
            value=score.value,
            source=score.source,
            status=score.status,
            eval_run_id=score.eval_run_id,
            author_user_id=score.author_user_id,
            reason=score.reason,
            environment=score.environment,
            config_id=score.config_id,
            metadata_=score.metadata,
            created_at=score.created_at,
            updated_at=score.updated_at,
        )
        self._session.add(row)
        await self._session.flush()
        return score

    async def get_session_scores_for_session(self, session_id: str, project_id: UUID) -> list[SessionScore]:
        """Fetch all scores for a specific session."""
        stmt = (
            select(SessionScoreModel)
            .where(SessionScoreModel.session_id == session_id, SessionScoreModel.project_id == project_id)
            .order_by(SessionScoreModel.created_at.desc())
        )
        result = await self._session.execute(stmt)
        return [self._to_session_score(row) for row in result.scalars().all()]

    async def get_session_scores_for_run(self, run_id: UUID, project_id: UUID) -> list[SessionScore]:
        """Fetch all session scores belonging to a specific eval run."""
        stmt = (
            select(SessionScoreModel)
            .where(SessionScoreModel.eval_run_id == run_id, SessionScoreModel.project_id == project_id)
            .order_by(SessionScoreModel.created_at.desc())
        )
        result = await self._session.execute(stmt)
        return [self._to_session_score(row) for row in result.scalars().all()]

    async def list_session_scores(
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
        """Paginated listing of session scores with filters."""
        t = SessionScoreModel.__table__
        base = select(t).where(t.c.project_id == project_id)

        if name is not None:
            base = base.where(t.c.name == name)
        if session_id is not None:
            base = base.where(t.c.session_id == session_id)
        if source is not None:
            base = base.where(t.c.source == source.value)
        if status is not None:
            base = base.where(t.c.status == status.value)
        if eval_run_id is not None:
            base = base.where(t.c.eval_run_id == eval_run_id)
        if date_from is not None:
            base = base.where(t.c.created_at >= date_from)
        if date_to is not None:
            base = base.where(t.c.created_at < date_to)

        count_stmt = select(func.count()).select_from(base.subquery())
        total = (await self._session.execute(count_stmt)).scalar_one()

        data_stmt = base.order_by(t.c.created_at.desc()).offset(offset).limit(limit)
        result = await self._session.execute(data_stmt)
        scores = [self._to_session_score_from_row(r) for r in result.mappings().all()]
        return scores, total

    async def get_failed_session_scores_for_run(self, run_id: UUID, project_id: UUID) -> list[SessionScore]:
        """Fetch FAILED session scores belonging to a specific eval run."""
        stmt = select(SessionScoreModel).where(
            SessionScoreModel.eval_run_id == run_id,
            SessionScoreModel.project_id == project_id,
            SessionScoreModel.status == ScoreStatus.FAILED.value,
        )
        result = await self._session.execute(stmt)
        return [self._to_session_score(row) for row in result.scalars().all()]

    async def delete_session_scores_for_run(self, run_id: UUID, project_id: UUID) -> int:
        """Delete all session scores belonging to a specific eval run."""
        stmt = delete(SessionScoreModel).where(
            SessionScoreModel.eval_run_id == run_id, SessionScoreModel.project_id == project_id
        )
        result = await self._session.execute(stmt)
        return result.rowcount

    async def delete_session_score(self, score_id: UUID, project_id: UUID) -> None:
        """Delete a single session score."""
        stmt = delete(SessionScoreModel).where(
            SessionScoreModel.id == score_id, SessionScoreModel.project_id == project_id
        )
        await self._session.execute(stmt)

    async def get_session_score_summary(
        self,
        project_id: UUID,
        *,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> list[dict[str, Any]]:
        """Aggregated session score summary grouped by metric."""
        t = SessionScoreModel.__table__
        numeric_value = cast(t.c.value, SAFloat)
        is_success = t.c.status == ScoreStatus.SUCCESS.value
        is_numeric_success = (t.c.data_type == ScoreDataType.NUMERIC.value) & is_success

        base = select(
            t.c.name.label("metric_name"),
            func.count().filter(is_success).label("success_count"),
            func.count().filter(t.c.status == ScoreStatus.FAILED.value).label("failed_count"),
            func.avg(numeric_value).filter(is_numeric_success).label("avg_score"),
            func.min(numeric_value).filter(is_numeric_success).label("min_score"),
            func.max(numeric_value).filter(is_numeric_success).label("max_score"),
            func.percentile_cont(0.5).within_group(numeric_value).filter(is_numeric_success).label("median_score"),
            func.max(t.c.created_at).label("latest_score_at"),
        ).where(t.c.project_id == project_id)

        if date_from is not None:
            base = base.where(t.c.created_at >= date_from)
        if date_to is not None:
            base = base.where(t.c.created_at < date_to)

        base = base.group_by(t.c.name)
        result = await self._session.execute(base)
        return [
            {
                "metric_name": row.metric_name,
                "avg_score": float(row.avg_score) if row.avg_score is not None else None,
                "min_score": float(row.min_score) if row.min_score is not None else None,
                "max_score": float(row.max_score) if row.max_score is not None else None,
                "median_score": float(row.median_score) if row.median_score is not None else None,
                "success_count": row.success_count,
                "failed_count": row.failed_count,
                "latest_score_at": row.latest_score_at.isoformat() if row.latest_score_at else None,
            }
            for row in result.all()
        ]

    async def get_session_score_trend(
        self,
        project_id: UUID,
        *,
        metric_name: str,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        granularity: AnalyticsGranularity = AnalyticsGranularity.DAY,
    ) -> list[dict[str, Any]]:
        """Time series of average session scores for a metric."""
        t = SessionScoreModel.__table__
        numeric_value = cast(t.c.value, SAFloat)
        bucket = func.date_trunc(granularity.value, t.c.created_at).label("bucket")

        base = select(
            bucket,
            t.c.name.label("metric_name"),
            func.avg(numeric_value).label("avg_score"),
            func.count().label("count"),
        ).where(
            t.c.project_id == project_id,
            t.c.name == metric_name,
            t.c.data_type == ScoreDataType.NUMERIC.value,
            t.c.status == ScoreStatus.SUCCESS.value,
        )

        if date_from is not None:
            base = base.where(t.c.created_at >= date_from)
        if date_to is not None:
            base = base.where(t.c.created_at < date_to)

        base = base.group_by(bucket, t.c.name).order_by(bucket)
        result = await self._session.execute(base)
        return [
            {
                "bucket": row.bucket.isoformat() if row.bucket else None,
                "metric_name": row.metric_name,
                "avg_score": float(row.avg_score) if row.avg_score is not None else 0.0,
                "count": row.count,
            }
            for row in result.all()
        ]

    async def get_session_score_distribution(
        self,
        project_id: UUID,
        metric_name: str,
        *,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        buckets: int = 10,
    ) -> list[dict[str, Any]]:
        """Histogram of session score values for a metric."""
        t = SessionScoreModel.__table__
        numeric_value = cast(t.c.value, SAFloat)
        bucket_col = func.width_bucket(numeric_value, 0.0, 1.0, buckets)

        base = select(
            bucket_col.label("bucket"),
            func.count().label("count"),
        ).where(
            t.c.project_id == project_id,
            t.c.name == metric_name,
            t.c.data_type == ScoreDataType.NUMERIC.value,
            t.c.status == ScoreStatus.SUCCESS.value,
        )

        if date_from is not None:
            base = base.where(t.c.created_at >= date_from)
        if date_to is not None:
            base = base.where(t.c.created_at < date_to)

        base = base.group_by(bucket_col).order_by(bucket_col)
        result = await self._session.execute(base)

        step = 1.0 / buckets
        return [
            {
                "bucket": row.bucket,
                "bucket_min": round(max(0.0, (row.bucket - 1) * step), 4),
                "bucket_max": round(min(1.0, row.bucket * step), 4),
                "count": row.count,
            }
            for row in result.all()
        ]

    async def get_session_score_history(
        self,
        project_id: UUID,
        session_id: str,
        *,
        metric_name: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Score evolution for a specific session across eval runs over time.

        Returns one row per (metric, eval_run) ordered by score creation time,
        showing how the session's scores changed as it was re-evaluated.
        """
        t = SessionScoreModel.__table__

        base = select(
            t.c.name.label("metric_name"),
            cast(t.c.value, SAFloat).label("score"),
            t.c.eval_run_id,
            t.c.created_at,
            t.c.status,
        ).where(
            t.c.project_id == project_id,
            t.c.session_id == session_id,
            t.c.data_type == ScoreDataType.NUMERIC.value,
        )

        if metric_name is not None:
            base = base.where(t.c.name == metric_name)

        base = base.order_by(t.c.created_at.asc()).limit(limit)
        result = await self._session.execute(base)
        return [
            {
                "metric_name": row.metric_name,
                "score": float(row.score) if row.score is not None else None,
                "eval_run_id": str(row.eval_run_id) if row.eval_run_id else None,
                "created_at": row.created_at.isoformat() if row.created_at else None,
                "status": row.status,
            }
            for row in result.all()
        ]

    async def get_session_score_comparison(
        self,
        project_id: UUID,
        metric_name: str,
        *,
        sort_order: str = "asc",
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        """Leaderboard: latest score per session for a given metric, sorted by value.

        Uses DISTINCT ON to pick the most recent score per session, then
        sorts by score value for ranking.
        """
        t = SessionScoreModel.__table__

        latest = (
            select(
                t.c.session_id,
                cast(t.c.value, SAFloat).label("score"),
                t.c.created_at,
                t.c.eval_run_id,
            )
            .where(
                t.c.project_id == project_id,
                t.c.name == metric_name,
                t.c.data_type == ScoreDataType.NUMERIC.value,
                t.c.status == ScoreStatus.SUCCESS.value,
            )
            .distinct(t.c.session_id)
            .order_by(t.c.session_id, t.c.created_at.desc())
        ).subquery("latest")

        count_stmt = select(func.count()).select_from(latest)
        total = (await self._session.execute(count_stmt)).scalar_one()

        order_col = latest.c.score.asc() if sort_order == "asc" else latest.c.score.desc()
        data_stmt = select(latest).order_by(order_col.nulls_last(), latest.c.session_id).offset(offset).limit(limit)
        result = await self._session.execute(data_stmt)
        rows = [
            {
                "session_id": row.session_id,
                "score": float(row.score) if row.score is not None else None,
                "evaluated_at": row.created_at.isoformat() if row.created_at else None,
                "eval_run_id": str(row.eval_run_id) if row.eval_run_id else None,
            }
            for row in result.all()
        ]
        return rows, total

    async def find_existing_trace_score(self, trace_id: UUID, metric_name: str) -> TraceScore | None:
        """Find the most recent successful trace score for a trace + metric."""
        stmt = (
            select(TraceScoreModel)
            .where(
                TraceScoreModel.trace_id == trace_id,
                TraceScoreModel.name == metric_name,
                TraceScoreModel.status == ScoreStatus.SUCCESS.value,
            )
            .order_by(TraceScoreModel.created_at.desc())
            .limit(1)
        )
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return self._to_score(row)

    # -- Mappers ---------------------------------------------------------------

    @staticmethod
    def _to_session_score(row: SessionScoreModel) -> SessionScore:
        return SessionScore(
            id=row.id,
            session_id=row.session_id,
            project_id=row.project_id,
            name=row.name,
            data_type=ScoreDataType(row.data_type),
            value=row.value,
            source=ScoreSource(row.source),
            status=ScoreStatus(row.status),
            eval_run_id=row.eval_run_id,
            author_user_id=row.author_user_id,
            reason=row.reason,
            environment=row.environment,
            config_id=row.config_id,
            metadata=row.metadata_,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    @staticmethod
    def _to_session_score_from_row(r: Any) -> SessionScore:
        return SessionScore(
            id=r["id"],
            session_id=r["session_id"],
            project_id=r["project_id"],
            name=r["name"],
            data_type=ScoreDataType(r["data_type"]),
            value=r["value"],
            source=ScoreSource(r["source"]),
            status=ScoreStatus(r["status"]),
            eval_run_id=r["eval_run_id"],
            author_user_id=r["author_user_id"],
            reason=r["reason"],
            environment=r["environment"],
            config_id=r["config_id"],
            metadata=r["metadata"],
            created_at=r["created_at"],
            updated_at=r["updated_at"],
        )

    @staticmethod
    def _to_score(row: TraceScoreModel) -> TraceScore:
        return TraceScore(
            id=row.id,
            trace_id=row.trace_id,
            project_id=row.project_id,
            name=row.name,
            data_type=ScoreDataType(row.data_type),
            value=row.value,
            source=ScoreSource(row.source),
            status=ScoreStatus(row.status),
            eval_run_id=row.eval_run_id,
            author_user_id=row.author_user_id,
            reason=row.reason,
            environment=row.environment,
            config_id=row.config_id,
            metadata=row.metadata_,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    @staticmethod
    def _to_score_from_row(r: Any) -> TraceScore:
        return TraceScore(
            id=r["id"],
            trace_id=r["trace_id"],
            project_id=r["project_id"],
            name=r["name"],
            data_type=ScoreDataType(r["data_type"]),
            value=r["value"],
            source=ScoreSource(r["source"]),
            status=ScoreStatus(r["status"]),
            eval_run_id=r["eval_run_id"],
            author_user_id=r["author_user_id"],
            reason=r["reason"],
            environment=r["environment"],
            config_id=r["config_id"],
            metadata=r["metadata"],
            created_at=r["created_at"],
            updated_at=r["updated_at"],
        )

    @staticmethod
    def _to_eval_run(row: EvalRunModel) -> EvalRun:
        return EvalRun(
            id=row.id,
            project_id=row.project_id,
            name=row.name,
            target_type=row.target_type,
            metric_names=row.metric_names,
            filters=row.filters,
            sampling_rate=row.sampling_rate,
            model=row.model,
            monitor_id=row.monitor_id,
            status=EvaluationStatus(row.status),
            total_traces=row.total_traces,
            evaluated_count=row.evaluated_count,
            failed_count=row.failed_count,
            error_message=row.error_message,
            created_at=row.created_at,
            completed_at=row.completed_at,
        )

    @staticmethod
    def _to_eval_run_from_row(r: Any) -> EvalRun:
        return EvalRun(
            id=r["id"],
            project_id=r["project_id"],
            name=r["name"],
            target_type=r["target_type"],
            metric_names=r["metric_names"],
            filters=r["filters"],
            sampling_rate=r["sampling_rate"],
            model=r["model"],
            monitor_id=r["monitor_id"],
            status=EvaluationStatus(r["status"]),
            total_traces=r["total_traces"],
            evaluated_count=r["evaluated_count"],
            failed_count=r["failed_count"],
            error_message=r["error_message"],
            created_at=r["created_at"],
            completed_at=r["completed_at"],
        )

    # -- Monitor operations ----------------------------------------------------

    async def create_monitor(self, monitor: EvalMonitor) -> EvalMonitor:
        """Persist a new eval monitor."""
        row = EvalMonitorModel(
            id=monitor.id,
            project_id=monitor.project_id,
            name=monitor.name,
            target_type=monitor.target_type,
            metric_names=monitor.metric_names,
            filters=monitor.filters,
            sampling_rate=monitor.sampling_rate,
            model=monitor.model,
            cadence=monitor.cadence,
            only_if_changed=monitor.only_if_changed,
            status=monitor.status,
            last_run_at=monitor.last_run_at,
            last_run_id=monitor.last_run_id,
            next_run_at=monitor.next_run_at,
            created_at=monitor.created_at,
            updated_at=monitor.updated_at,
        )
        self._session.add(row)
        await self._session.flush()
        return monitor

    async def get_monitor(self, monitor_id: UUID, project_id: UUID) -> EvalMonitor | None:
        """Fetch a monitor by ID scoped to a project."""
        stmt = select(EvalMonitorModel).where(
            EvalMonitorModel.id == monitor_id,
            EvalMonitorModel.project_id == project_id,
        )
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return self._to_monitor(row)

    async def list_monitors(
        self,
        project_id: UUID,
        *,
        status: MonitorStatus | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[EvalMonitor], int]:
        """Paginated listing of monitors."""
        t = EvalMonitorModel.__table__
        base = select(t).where(t.c.project_id == project_id)
        if status is not None:
            base = base.where(t.c.status == status.value)

        count_stmt = select(func.count()).select_from(base.subquery())
        total = (await self._session.execute(count_stmt)).scalar_one()

        data_stmt = base.order_by(t.c.created_at.desc()).offset(offset).limit(limit)
        result = await self._session.execute(data_stmt)
        monitors = [self._to_monitor_from_row(r) for r in result.mappings().all()]
        return monitors, total

    async def update_monitor(self, monitor_id: UUID, project_id: UUID, **fields: Any) -> None:
        """Partial update of monitor fields.

        Fields with None values are applied if explicitly passed (e.g.
        next_run_at=None to clear the scheduled time on pause).
        """
        if not fields:
            return
        values = dict(fields)
        values["updated_at"] = datetime.now(timezone.utc)
        stmt = (
            update(EvalMonitorModel)
            .where(EvalMonitorModel.id == monitor_id, EvalMonitorModel.project_id == project_id)
            .values(**values)
        )
        await self._session.execute(stmt)

    async def delete_monitor(self, monitor_id: UUID, project_id: UUID) -> None:
        """Delete a monitor. Spawned runs are preserved (FK SET NULL)."""
        stmt = delete(EvalMonitorModel).where(
            EvalMonitorModel.id == monitor_id, EvalMonitorModel.project_id == project_id
        )
        await self._session.execute(stmt)

    async def get_due_monitors(self, now: datetime) -> list[EvalMonitor]:
        """Return all ACTIVE monitors whose next_run_at <= now."""
        stmt = (
            select(EvalMonitorModel)
            .where(
                EvalMonitorModel.status == MonitorStatus.ACTIVE.value,
                EvalMonitorModel.next_run_at <= now,
            )
            .order_by(EvalMonitorModel.next_run_at.asc())
        )
        result = await self._session.execute(stmt)
        return [self._to_monitor(row) for row in result.scalars().all()]

    async def advance_monitor(
        self,
        monitor_id: UUID,
        *,
        last_run_at: datetime,
        last_run_id: UUID | None,
        next_run_at: datetime,
    ) -> None:
        """Advance a monitor's scheduling state after spawning (or skipping) a run."""
        stmt = (
            update(EvalMonitorModel)
            .where(EvalMonitorModel.id == monitor_id)
            .values(
                last_run_at=last_run_at,
                last_run_id=last_run_id,
                next_run_at=next_run_at,
                updated_at=datetime.now(timezone.utc),
            )
        )
        await self._session.execute(stmt)

    async def list_runs_for_monitor(
        self,
        monitor_id: UUID,
        project_id: UUID,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[EvalRun], int]:
        """List eval runs spawned by a specific monitor."""
        t = EvalRunModel.__table__
        base = select(t).where(t.c.monitor_id == monitor_id, t.c.project_id == project_id)

        count_stmt = select(func.count()).select_from(base.subquery())
        total = (await self._session.execute(count_stmt)).scalar_one()

        data_stmt = base.order_by(t.c.created_at.desc()).offset(offset).limit(limit)
        result = await self._session.execute(data_stmt)
        runs = [self._to_eval_run_from_row(r) for r in result.mappings().all()]
        return runs, total

    @staticmethod
    def _to_monitor(row: EvalMonitorModel) -> EvalMonitor:
        return EvalMonitor(
            id=row.id,
            project_id=row.project_id,
            name=row.name,
            target_type=row.target_type,
            metric_names=row.metric_names,
            filters=row.filters,
            sampling_rate=row.sampling_rate,
            model=row.model,
            cadence=row.cadence,
            only_if_changed=row.only_if_changed,
            status=row.status,
            last_run_at=row.last_run_at,
            last_run_id=row.last_run_id,
            next_run_at=row.next_run_at,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    @staticmethod
    def _to_monitor_from_row(r: Any) -> EvalMonitor:
        return EvalMonitor(
            id=r["id"],
            project_id=r["project_id"],
            name=r["name"],
            target_type=r["target_type"],
            metric_names=r["metric_names"],
            filters=r["filters"],
            sampling_rate=r["sampling_rate"],
            model=r["model"],
            cadence=r["cadence"],
            only_if_changed=r["only_if_changed"],
            status=r["status"],
            last_run_at=r["last_run_at"],
            last_run_id=r["last_run_id"],
            next_run_at=r["next_run_at"],
            created_at=r["created_at"],
            updated_at=r["updated_at"],
        )
