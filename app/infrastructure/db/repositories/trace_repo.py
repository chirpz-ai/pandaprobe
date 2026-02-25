"""PostgreSQL implementation of the Trace repository.

Translates between ORM models and pure domain entities for traces
and their child spans.
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import Row, cast, delete, func, select, text, update
from sqlalchemy.dialects.postgresql import ARRAY as PG_ARRAY
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.types import Float, Integer, String

from app.core.traces.entities import Span, Trace
from app.infrastructure.db.models import SpanModel, TraceModel
from app.registry.constants import (
    AnalyticsGranularity,
    SessionSortBy,
    SortOrder,
    SpanKind,
    SpanStatusCode,
    TraceSortBy,
    TraceStatus,
)

# Sentinel to distinguish "field not provided" from "field set to None"
_UNSET = object()


class TraceRepository:
    """Concrete trace repository backed by PostgreSQL + SQLAlchemy."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # -- Upsert ----------------------------------------------------------

    async def upsert_trace(self, trace: Trace) -> Trace:
        """Insert or merge a trace and its spans using ON CONFLICT.

        Merge semantics:
        - Non-null incoming scalar fields overwrite existing values.
        - ``metadata`` is shallow-merged (existing || incoming).
        - ``tags`` are union-merged (array of distinct values).
        """
        t = TraceModel.__table__
        vals: dict[str, Any] = dict(
            trace_id=trace.trace_id,
            project_id=trace.project_id,
            name=trace.name,
            status=trace.status.value,
            input=trace.input,
            output=trace.output,
            metadata=trace.metadata,
            started_at=trace.started_at,
            ended_at=trace.ended_at,
            session_id=trace.session_id,
            user_id=trace.user_id,
            tags=trace.tags,
            environment=trace.environment,
            release=trace.release,
        )

        stmt = pg_insert(t).values(**vals)
        stmt = stmt.on_conflict_do_update(
            index_elements=["trace_id"],
            set_=dict(
                name=stmt.excluded.name,
                status=stmt.excluded.status,
                input=func.coalesce(stmt.excluded.input, t.c.input),
                output=func.coalesce(stmt.excluded.output, t.c.output),
                metadata=func.coalesce(t.c.metadata, text("'{}'::jsonb"))
                + func.coalesce(stmt.excluded.metadata, text("'{}'::jsonb")),
                started_at=stmt.excluded.started_at,
                ended_at=func.coalesce(stmt.excluded.ended_at, t.c.ended_at),
                session_id=func.coalesce(stmt.excluded.session_id, t.c.session_id),
                user_id=func.coalesce(stmt.excluded.user_id, t.c.user_id),
                tags=func.coalesce(
                    cast(
                        select(func.array_agg(func.distinct(text("unnest_val"))))
                        .select_from(func.unnest(t.c.tags + stmt.excluded.tags).alias("unnest_val"))
                        .correlate(t)
                        .scalar_subquery(),
                        PG_ARRAY(String),
                    ),
                    stmt.excluded.tags,
                ),
                environment=func.coalesce(stmt.excluded.environment, t.c.environment),
                release=func.coalesce(stmt.excluded.release, t.c.release),
            ),
        )
        await self._session.execute(stmt)

        for span in trace.spans:
            await self._upsert_span(span)

        await self._session.flush()
        return trace

    async def _upsert_span(self, span: Span) -> None:
        """Insert or merge a single span using ON CONFLICT."""
        s = SpanModel.__table__
        vals: dict[str, Any] = dict(
            span_id=span.span_id,
            trace_id=span.trace_id,
            parent_span_id=span.parent_span_id,
            name=span.name,
            kind=span.kind.value,
            status=span.status.value,
            input=span.input,
            output=span.output,
            model=span.model,
            token_usage=span.token_usage,
            metadata=span.metadata,
            started_at=span.started_at,
            ended_at=span.ended_at,
            error=span.error,
            completion_start_time=span.completion_start_time,
            model_parameters=span.model_parameters,
            cost=span.cost,
        )

        stmt = pg_insert(s).values(**vals)
        stmt = stmt.on_conflict_do_update(
            index_elements=["span_id"],
            set_=dict(
                name=stmt.excluded.name,
                kind=stmt.excluded.kind,
                status=stmt.excluded.status,
                input=func.coalesce(stmt.excluded.input, s.c.input),
                output=func.coalesce(stmt.excluded.output, s.c.output),
                model=func.coalesce(stmt.excluded.model, s.c.model),
                token_usage=func.coalesce(stmt.excluded.token_usage, s.c.token_usage),
                metadata=func.coalesce(s.c.metadata, text("'{}'::jsonb"))
                + func.coalesce(stmt.excluded.metadata, text("'{}'::jsonb")),
                started_at=stmt.excluded.started_at,
                ended_at=func.coalesce(stmt.excluded.ended_at, s.c.ended_at),
                error=func.coalesce(stmt.excluded.error, s.c.error),
                completion_start_time=func.coalesce(stmt.excluded.completion_start_time, s.c.completion_start_time),
                model_parameters=func.coalesce(stmt.excluded.model_parameters, s.c.model_parameters),
                cost=func.coalesce(stmt.excluded.cost, s.c.cost),
            ),
        )
        await self._session.execute(stmt)

    # -- Update -----------------------------------------------------------

    async def update_trace(
        self,
        trace_id: UUID,
        project_id: UUID,
        **fields: Any,
    ) -> TraceModel | None:
        """Selectively update trace fields.  Returns the updated ORM row or None."""
        stmt = (
            select(TraceModel)
            .options(selectinload(TraceModel.spans))
            .where(TraceModel.trace_id == trace_id, TraceModel.project_id == project_id)
        )
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        if row is None:
            return None

        for key, value in fields.items():
            if value is _UNSET:
                continue
            if key == "metadata":
                existing = row.metadata_ or {}
                row.metadata_ = {**existing, **(value or {})}
            elif key == "status" and value is not None:
                row.status = value.value if hasattr(value, "value") else value
            else:
                setattr(row, key, value)

        await self._session.flush()
        return row

    async def update_span(
        self,
        span_id: UUID,
        trace_id: UUID,
        project_id: UUID,
        **fields: Any,
    ) -> SpanModel | None:
        """Selectively update span fields.  Returns the updated ORM row or None."""
        stmt = (
            select(SpanModel)
            .join(TraceModel, SpanModel.trace_id == TraceModel.trace_id)
            .where(
                SpanModel.span_id == span_id,
                SpanModel.trace_id == trace_id,
                TraceModel.project_id == project_id,
            )
        )
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        if row is None:
            return None

        for key, value in fields.items():
            if value is _UNSET:
                continue
            if key == "metadata":
                existing = row.metadata_ or {}
                row.metadata_ = {**existing, **(value or {})}
            elif key == "status" and value is not None:
                row.status = value.value if hasattr(value, "value") else value
            elif key == "kind" and value is not None:
                row.kind = value.value if hasattr(value, "value") else value
            else:
                setattr(row, key, value)

        await self._session.flush()
        return row

    # -- Span ingestion ---------------------------------------------------

    async def add_spans(
        self,
        trace_id: UUID,
        project_id: UUID,
        spans: list[Span],
    ) -> bool:
        """Bulk-upsert spans onto an existing trace.  Returns False if trace not found."""
        exists = (
            await self._session.execute(
                select(TraceModel.trace_id).where(
                    TraceModel.trace_id == trace_id,
                    TraceModel.project_id == project_id,
                )
            )
        ).scalar_one_or_none()
        if exists is None:
            return False

        for span in spans:
            await self._upsert_span(span)
        await self._session.flush()
        return True

    # -- Read ------------------------------------------------------------------

    async def get_trace(self, trace_id: UUID, project_id: UUID) -> Trace | None:
        """Load a trace with its spans, scoped to a project."""
        stmt = (
            select(TraceModel)
            .options(selectinload(TraceModel.spans))
            .where(TraceModel.trace_id == trace_id, TraceModel.project_id == project_id)
        )
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        return self._to_trace(row) if row else None

    async def list_traces(
        self,
        project_id: UUID,
        limit: int = 50,
        offset: int = 0,
        *,
        session_id: str | None = None,
        status: TraceStatus | None = None,
        user_id: str | None = None,
        tags: list[str] | None = None,
        name: str | None = None,
        started_after: datetime | None = None,
        started_before: datetime | None = None,
        sort_by: TraceSortBy = TraceSortBy.STARTED_AT,
        sort_order: SortOrder = SortOrder.DESC,
    ) -> tuple[list[Row[Any]], int]:
        """Return paginated trace rows with computed stats and total count.

        Each returned Row has the TraceModel columns plus:
        span_count, total_tokens, total_cost, latency_ms.
        """
        t = TraceModel.__table__

        span_stats = (
            select(
                SpanModel.trace_id.label("_trace_id"),
                func.count(SpanModel.span_id).label("span_count"),
                func.sum(
                    func.coalesce(cast(SpanModel.token_usage["prompt_tokens"].astext, Integer), 0)
                    + func.coalesce(cast(SpanModel.token_usage["completion_tokens"].astext, Integer), 0)
                ).label("total_tokens"),
                func.sum(func.coalesce(cast(SpanModel.cost["total"].astext, Float), 0)).label("total_cost"),
            )
            .group_by(SpanModel.trace_id)
            .subquery("span_stats")
        )

        latency_expr = func.extract("epoch", t.c.ended_at - t.c.started_at) * 1000

        base = (
            select(
                t,
                func.coalesce(span_stats.c.span_count, 0).label("span_count"),
                func.coalesce(span_stats.c.total_tokens, 0).label("total_tokens"),
                func.coalesce(span_stats.c.total_cost, 0.0).label("total_cost"),
                latency_expr.label("latency_ms"),
            )
            .outerjoin(span_stats, t.c.trace_id == span_stats.c._trace_id)
            .where(t.c.project_id == project_id)
        )

        base = self._apply_trace_filters(
            base,
            t,
            session_id=session_id,
            status=status,
            user_id=user_id,
            tags=tags,
            name=name,
            started_after=started_after,
            started_before=started_before,
        )

        count_stmt = select(func.count()).select_from(base.with_only_columns(t.c.trace_id).subquery())
        total = (await self._session.execute(count_stmt)).scalar_one()

        sort_col = self._resolve_sort_column(sort_by, t, latency_expr)
        direction = sort_col.asc() if sort_order == SortOrder.ASC else sort_col.desc()

        data_stmt = base.order_by(direction).offset(offset).limit(limit)
        rows = (await self._session.execute(data_stmt)).all()

        return rows, total

    # -- Delete -----------------------------------------------------------

    async def delete_trace(self, trace_id: UUID, project_id: UUID) -> bool:
        """Hard-delete a trace (CASCADE removes spans).  Returns False if not found."""
        result = await self._session.execute(
            delete(TraceModel).where(
                TraceModel.trace_id == trace_id,
                TraceModel.project_id == project_id,
            )
        )
        return result.rowcount > 0  # type: ignore[union-attr]

    # -- Batch ops --------------------------------------------------------

    async def batch_delete_traces(
        self,
        project_id: UUID,
        trace_ids: list[UUID],
    ) -> int:
        """Delete multiple traces.  Returns the number of rows removed."""
        result = await self._session.execute(
            delete(TraceModel).where(
                TraceModel.project_id == project_id,
                TraceModel.trace_id.in_(trace_ids),
            )
        )
        return result.rowcount  # type: ignore[union-attr]

    async def batch_update_tags(
        self,
        project_id: UUID,
        trace_ids: list[UUID],
        add_tags: list[str] | None = None,
        remove_tags: list[str] | None = None,
    ) -> int:
        """Add and/or remove tags on multiple traces.  Returns rows affected."""
        stmt = select(TraceModel).where(
            TraceModel.project_id == project_id,
            TraceModel.trace_id.in_(trace_ids),
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        count = 0
        for row in rows:
            current: list[str] = list(row.tags or [])
            if add_tags:
                for tag in add_tags:
                    if tag not in current:
                        current.append(tag)
            if remove_tags:
                current = [t for t in current if t not in remove_tags]
            row.tags = current
            count += 1
        await self._session.flush()
        return count

    # -- Session aggregation ---------------------------------------------------

    def _session_span_stats_subquery(self) -> Any:
        """Subquery: span-level stats grouped by trace_id (reusable)."""
        return (
            select(
                SpanModel.trace_id.label("_trace_id"),
                func.count(SpanModel.span_id).label("span_count"),
                func.sum(
                    func.coalesce(cast(SpanModel.token_usage["prompt_tokens"].astext, Integer), 0)
                    + func.coalesce(cast(SpanModel.token_usage["completion_tokens"].astext, Integer), 0)
                ).label("total_tokens"),
                func.sum(func.coalesce(cast(SpanModel.cost["total"].astext, Float), 0)).label("total_cost"),
            )
            .group_by(SpanModel.trace_id)
            .subquery("span_stats")
        )

    async def list_sessions(
        self,
        project_id: UUID,
        limit: int = 50,
        offset: int = 0,
        *,
        user_id: str | None = None,
        has_error: bool | None = None,
        started_after: datetime | None = None,
        started_before: datetime | None = None,
        tags: list[str] | None = None,
        query: str | None = None,
        sort_by: SessionSortBy = SessionSortBy.RECENT,
        sort_order: SortOrder = SortOrder.DESC,
    ) -> tuple[list[Row[Any]], int]:
        """Return aggregated session summaries with total count."""
        t = TraceModel.__table__.alias("t")
        span_stats = self._session_span_stats_subquery()

        base_where = [t.c.project_id == project_id, t.c.session_id.isnot(None)]
        if started_after is not None:
            base_where.append(t.c.started_at >= started_after)
        if started_before is not None:
            base_where.append(t.c.started_at < started_before)
        if user_id is not None:
            base_where.append(t.c.user_id == user_id)
        if tags:
            base_where.append(t.c.tags.overlap(tags))
        if query:
            base_where.append(t.c.session_id.ilike(f"%{query}%"))

        total_tokens_expr = func.coalesce(func.sum(span_stats.c.total_tokens), 0)
        total_cost_expr = func.coalesce(func.sum(span_stats.c.total_cost), 0.0)
        total_span_count_expr = func.coalesce(func.sum(span_stats.c.span_count), 0)
        total_latency_expr = func.sum(func.extract("epoch", t.c.ended_at - t.c.started_at) * 1000)

        agg_stmt = (
            select(
                t.c.session_id,
                func.count(t.c.trace_id).label("trace_count"),
                func.min(t.c.started_at).label("first_trace_at"),
                func.max(t.c.ended_at).label("last_trace_at"),
                total_latency_expr.label("total_latency_ms"),
                func.bool_or(t.c.status == TraceStatus.ERROR.value).label("has_error"),
                (
                    select(TraceModel.user_id)
                    .where(
                        TraceModel.project_id == project_id,
                        TraceModel.session_id == t.c.session_id,
                        TraceModel.user_id.isnot(None),
                    )
                    .order_by(TraceModel.started_at.asc())
                    .limit(1)
                    .correlate(t)
                    .scalar_subquery()
                    .label("user_id")
                ),
                func.coalesce(
                    cast(
                        select(func.array_agg(func.distinct(func.unnest(TraceModel.tags))))
                        .where(
                            TraceModel.project_id == project_id,
                            TraceModel.session_id == t.c.session_id,
                        )
                        .correlate(t)
                        .scalar_subquery(),
                        PG_ARRAY(String),
                    ),
                    text("'{}'"),
                ).label("tags"),
                total_span_count_expr.label("total_span_count"),
                total_tokens_expr.label("total_tokens"),
                total_cost_expr.label("total_cost"),
            )
            .outerjoin(span_stats, t.c.trace_id == span_stats.c._trace_id)
            .where(*base_where)
            .group_by(t.c.session_id)
        )

        if has_error is True:
            agg_stmt = agg_stmt.having(func.bool_or(t.c.status == TraceStatus.ERROR.value).is_(True))
        elif has_error is False:
            agg_stmt = agg_stmt.having(func.bool_or(t.c.status == TraceStatus.ERROR.value).is_(False))

        count_sub = agg_stmt.with_only_columns(t.c.session_id).subquery()
        total = (await self._session.execute(select(func.count()).select_from(count_sub))).scalar_one()

        sort_mapping: dict[SessionSortBy, Any] = {
            SessionSortBy.RECENT: func.max(t.c.created_at),
            SessionSortBy.TRACE_COUNT: func.count(t.c.trace_id),
            SessionSortBy.LATENCY: total_latency_expr,
            SessionSortBy.COST: total_cost_expr,
        }
        sort_col = sort_mapping.get(sort_by, func.max(t.c.created_at))
        direction = sort_col.asc() if sort_order == SortOrder.ASC else sort_col.desc()

        data_stmt = agg_stmt.order_by(direction).offset(offset).limit(limit)
        result = await self._session.execute(data_stmt)
        return list(result.all()), total

    async def get_session_summary(
        self,
        project_id: UUID,
        session_id: str,
    ) -> Row[Any] | None:
        """Return a single-row aggregated summary for one session.

        Includes trace-level aggregation (count, latency, error, tags)
        plus span-level rollups (span_count, tokens, cost) and session
        I/O (first trace input, last trace output).
        """
        t = TraceModel.__table__.alias("t")
        span_stats = self._session_span_stats_subquery()

        input_subq = (
            select(TraceModel.input)
            .where(
                TraceModel.project_id == project_id,
                TraceModel.session_id == session_id,
            )
            .order_by(TraceModel.started_at.asc())
            .limit(1)
            .scalar_subquery()
        )
        output_subq = (
            select(TraceModel.output)
            .where(
                TraceModel.project_id == project_id,
                TraceModel.session_id == session_id,
                TraceModel.output.isnot(None),
            )
            .order_by(TraceModel.started_at.desc())
            .limit(1)
            .scalar_subquery()
        )

        stmt = (
            select(
                t.c.session_id,
                func.count(t.c.trace_id).label("trace_count"),
                func.min(t.c.started_at).label("first_trace_at"),
                func.max(t.c.ended_at).label("last_trace_at"),
                func.sum(func.extract("epoch", t.c.ended_at - t.c.started_at) * 1000).label("total_latency_ms"),
                func.bool_or(t.c.status == TraceStatus.ERROR.value).label("has_error"),
                (
                    select(TraceModel.user_id)
                    .where(
                        TraceModel.project_id == project_id,
                        TraceModel.session_id == session_id,
                        TraceModel.user_id.isnot(None),
                    )
                    .order_by(TraceModel.started_at.asc())
                    .limit(1)
                    .correlate(t)
                    .scalar_subquery()
                    .label("user_id")
                ),
                func.coalesce(
                    cast(
                        select(func.array_agg(func.distinct(func.unnest(TraceModel.tags))))
                        .where(
                            TraceModel.project_id == project_id,
                            TraceModel.session_id == session_id,
                        )
                        .correlate(t)
                        .scalar_subquery(),
                        PG_ARRAY(String),
                    ),
                    text("'{}'"),
                ).label("tags"),
                func.coalesce(func.sum(span_stats.c.span_count), 0).label("total_span_count"),
                func.coalesce(func.sum(span_stats.c.total_tokens), 0).label("total_tokens"),
                func.coalesce(func.sum(span_stats.c.total_cost), 0.0).label("total_cost"),
                input_subq.label("input"),
                output_subq.label("output"),
            )
            .outerjoin(span_stats, t.c.trace_id == span_stats.c._trace_id)
            .where(t.c.project_id == project_id, t.c.session_id == session_id)
            .group_by(t.c.session_id)
        )
        return (await self._session.execute(stmt)).one_or_none()

    async def list_session_traces_with_stats(
        self,
        project_id: UUID,
        session_id: str,
        limit: int = 200,
        offset: int = 0,
    ) -> tuple[list[Row[Any]], int]:
        """Return paginated traces for a session with span statistics.

        Each Row contains trace columns plus span_count, total_tokens,
        total_cost, latency_ms — matching the shape of ``list_traces``.
        """
        t = TraceModel.__table__
        span_stats = self._session_span_stats_subquery()
        latency_expr = func.extract("epoch", t.c.ended_at - t.c.started_at) * 1000

        base = (
            select(
                t,
                func.coalesce(span_stats.c.span_count, 0).label("span_count"),
                func.coalesce(span_stats.c.total_tokens, 0).label("total_tokens"),
                func.coalesce(span_stats.c.total_cost, 0.0).label("total_cost"),
                latency_expr.label("latency_ms"),
            )
            .outerjoin(span_stats, t.c.trace_id == span_stats.c._trace_id)
            .where(t.c.project_id == project_id, t.c.session_id == session_id)
        )

        count_stmt = select(func.count()).select_from(base.with_only_columns(t.c.trace_id).subquery())
        total = (await self._session.execute(count_stmt)).scalar_one()

        data_stmt = base.order_by(t.c.started_at.asc()).offset(offset).limit(limit)
        rows = (await self._session.execute(data_stmt)).all()
        return rows, total

    async def delete_session(self, project_id: UUID, session_id: str) -> int:
        """Delete all traces (CASCADE removes spans) for a session.  Returns count."""
        result = await self._session.execute(
            delete(TraceModel).where(
                TraceModel.project_id == project_id,
                TraceModel.session_id == session_id,
            )
        )
        return result.rowcount  # type: ignore[union-attr]

    async def get_session_analytics(
        self,
        project_id: UUID,
        granularity: AnalyticsGranularity,
        started_after: datetime,
        started_before: datetime,
    ) -> list[Row[Any]]:
        """Time-bucketed session statistics.

        Uses a CTE that first aggregates per-session, then buckets those
        sessions by their first_trace_at.
        """
        t = TraceModel.__table__

        session_cte = (
            select(
                t.c.session_id,
                func.min(t.c.started_at).label("first_trace_at"),
                func.count(t.c.trace_id).label("trace_count"),
                func.sum(func.extract("epoch", t.c.ended_at - t.c.started_at) * 1000).label("duration_ms"),
            )
            .where(
                t.c.project_id == project_id,
                t.c.session_id.isnot(None),
                t.c.started_at >= started_after,
                t.c.started_at < started_before,
            )
            .group_by(t.c.session_id)
            .cte("session_cte")
        )

        stmt = (
            select(
                func.date_trunc(granularity.value, session_cte.c.first_trace_at).label("bucket"),
                func.count().label("session_count"),
                func.avg(session_cte.c.trace_count).label("avg_traces_per_session"),
                func.avg(session_cte.c.duration_ms).label("avg_session_duration_ms"),
            )
            .group_by(text("bucket"))
            .order_by(text("bucket"))
        )
        return list((await self._session.execute(stmt)).all())

    # -- Analytics --------------------------------------------------------

    async def get_trace_analytics(
        self,
        project_id: UUID,
        granularity: AnalyticsGranularity,
        started_after: datetime,
        started_before: datetime,
    ) -> list[Row[Any]]:
        """Return time-bucketed trace statistics (volume, errors, latency)."""
        t = TraceModel.__table__
        latency_secs = func.extract("epoch", t.c.ended_at - t.c.started_at)

        stmt = (
            select(
                func.date_trunc(granularity.value, t.c.started_at).label("bucket"),
                func.count().label("trace_count"),
                func.count().filter(t.c.status == TraceStatus.ERROR.value).label("error_count"),
                (func.avg(latency_secs) * 1000).label("avg_latency_ms"),
                func.percentile_cont(0.5).within_group(latency_secs).op("*")(1000).label("p50_latency_ms"),
                func.percentile_cont(0.9).within_group(latency_secs).op("*")(1000).label("p90_latency_ms"),
                func.percentile_cont(0.99).within_group(latency_secs).op("*")(1000).label("p99_latency_ms"),
            )
            .where(
                t.c.project_id == project_id,
                t.c.started_at >= started_after,
                t.c.started_at < started_before,
            )
            .group_by(text("bucket"))
            .order_by(text("bucket"))
        )
        return list((await self._session.execute(stmt)).all())

    async def get_token_cost_analytics(
        self,
        project_id: UUID,
        granularity: AnalyticsGranularity,
        started_after: datetime,
        started_before: datetime,
    ) -> list[Row[Any]]:
        """Return time-bucketed token usage and cost from spans."""
        s = SpanModel.__table__
        t = TraceModel.__table__

        stmt = (
            select(
                func.date_trunc(granularity.value, s.c.started_at).label("bucket"),
                func.sum(
                    func.coalesce(cast(s.c.token_usage["prompt_tokens"].astext, Integer), 0)
                    + func.coalesce(cast(s.c.token_usage["completion_tokens"].astext, Integer), 0)
                ).label("total_tokens"),
                func.sum(func.coalesce(cast(s.c.token_usage["prompt_tokens"].astext, Integer), 0)).label(
                    "prompt_tokens"
                ),
                func.sum(func.coalesce(cast(s.c.token_usage["completion_tokens"].astext, Integer), 0)).label(
                    "completion_tokens"
                ),
                func.sum(func.coalesce(cast(s.c.cost["total"].astext, Float), 0)).label("total_cost"),
            )
            .join(t, s.c.trace_id == t.c.trace_id)
            .where(
                t.c.project_id == project_id,
                s.c.started_at >= started_after,
                s.c.started_at < started_before,
            )
            .group_by(text("bucket"))
            .order_by(text("bucket"))
        )
        return list((await self._session.execute(stmt)).all())

    async def get_top_models(
        self,
        project_id: UUID,
        started_after: datetime,
        started_before: datetime,
        limit: int = 10,
    ) -> list[Row[Any]]:
        """Return the most-used LLM models within spans."""
        s = SpanModel.__table__
        t = TraceModel.__table__

        stmt = (
            select(
                s.c.model,
                func.count().label("call_count"),
                func.sum(
                    func.coalesce(cast(s.c.token_usage["prompt_tokens"].astext, Integer), 0)
                    + func.coalesce(cast(s.c.token_usage["completion_tokens"].astext, Integer), 0)
                ).label("total_tokens"),
                func.sum(func.coalesce(cast(s.c.cost["total"].astext, Float), 0)).label("total_cost"),
            )
            .join(t, s.c.trace_id == t.c.trace_id)
            .where(
                t.c.project_id == project_id,
                s.c.model.isnot(None),
                s.c.started_at >= started_after,
                s.c.started_at < started_before,
            )
            .group_by(s.c.model)
            .order_by(func.count().desc())
            .limit(limit)
        )
        return list((await self._session.execute(stmt)).all())

    # -- User aggregation -------------------------------------------------

    async def list_trace_users(
        self,
        project_id: UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[Row[Any]], int]:
        """Return user-level trace aggregation with total count."""
        t = TraceModel.__table__

        base = (
            select(
                t.c.user_id,
                func.count().label("trace_count"),
                func.min(t.c.started_at).label("first_seen"),
                func.max(t.c.started_at).label("last_seen"),
                func.count().filter(t.c.status == TraceStatus.ERROR.value).label("error_count"),
            )
            .where(t.c.project_id == project_id, t.c.user_id.isnot(None))
            .group_by(t.c.user_id)
        )

        count_sub = base.with_only_columns(t.c.user_id).subquery()
        total = (await self._session.execute(select(func.count()).select_from(count_sub))).scalar_one()

        data_stmt = base.order_by(func.max(t.c.started_at).desc()).offset(offset).limit(limit)
        rows = (await self._session.execute(data_stmt)).all()
        return list(rows), total

    # -- Filter helpers --------------------------------------------------------

    @staticmethod
    def _apply_trace_filters(
        stmt: Any,
        t: Any,
        *,
        session_id: str | None = None,
        status: TraceStatus | None = None,
        user_id: str | None = None,
        tags: list[str] | None = None,
        name: str | None = None,
        started_after: datetime | None = None,
        started_before: datetime | None = None,
    ) -> Any:
        if session_id is not None:
            stmt = stmt.where(t.c.session_id == session_id)
        if status is not None:
            stmt = stmt.where(t.c.status == status.value)
        if user_id is not None:
            stmt = stmt.where(t.c.user_id == user_id)
        if tags:
            stmt = stmt.where(t.c.tags.overlap(tags))
        if name:
            stmt = stmt.where(t.c.name.ilike(f"%{name}%"))
        if started_after is not None:
            stmt = stmt.where(t.c.started_at >= started_after)
        if started_before is not None:
            stmt = stmt.where(t.c.started_at < started_before)
        return stmt

    @staticmethod
    def _resolve_sort_column(sort_by: TraceSortBy, t: Any, latency_expr: Any) -> Any:
        mapping = {
            TraceSortBy.STARTED_AT: t.c.started_at,
            TraceSortBy.ENDED_AT: t.c.ended_at,
            TraceSortBy.NAME: t.c.name,
            TraceSortBy.STATUS: t.c.status,
            TraceSortBy.LATENCY: latency_expr,
        }
        return mapping.get(sort_by, t.c.started_at)

    # -- Mappers ---------------------------------------------------------------

    @staticmethod
    def _to_span(row: SpanModel) -> Span:
        return Span(
            span_id=row.span_id,
            trace_id=row.trace_id,
            parent_span_id=row.parent_span_id,
            name=row.name,
            kind=SpanKind(row.kind),
            status=SpanStatusCode(row.status),
            input=row.input,
            output=row.output,
            model=row.model,
            token_usage=row.token_usage,
            metadata=row.metadata_,
            started_at=row.started_at,
            ended_at=row.ended_at,
            error=row.error,
            completion_start_time=row.completion_start_time,
            model_parameters=row.model_parameters,
            cost=row.cost,
        )

    @classmethod
    def _to_trace(cls, row: TraceModel, *, include_spans: bool = True) -> Trace:
        spans = [cls._to_span(s) for s in row.spans] if include_spans and row.spans else []
        return Trace(
            trace_id=row.trace_id,
            project_id=row.project_id,
            name=row.name,
            status=TraceStatus(row.status),
            input=row.input,
            output=row.output,
            metadata=row.metadata_,
            started_at=row.started_at,
            ended_at=row.ended_at,
            session_id=row.session_id,
            user_id=row.user_id,
            tags=row.tags,
            environment=row.environment,
            release=row.release,
            spans=spans,
        )
