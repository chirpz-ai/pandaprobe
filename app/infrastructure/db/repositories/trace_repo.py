"""PostgreSQL implementation of the Trace repository.

Translates between ORM models and pure domain entities for traces
and their child spans.
"""

from typing import Any
from uuid import UUID

from sqlalchemy import Row, cast, func, select, text
from sqlalchemy.dialects.postgresql import ARRAY as PG_ARRAY
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.types import String

from app.core.traces.entities import Span, Trace
from app.infrastructure.db.models import SpanModel, TraceModel
from app.registry.constants import SpanKind, SpanStatusCode, TraceStatus


class TraceRepository:
    """Concrete trace repository backed by PostgreSQL + SQLAlchemy."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialise with an async database session."""
        self._session = session

    async def create_trace(self, trace: Trace) -> Trace:
        """Persist a trace together with all its spans in a single flush."""
        row = TraceModel(
            trace_id=trace.trace_id,
            project_id=trace.project_id,
            name=trace.name,
            status=trace.status.value,
            input=trace.input,
            output=trace.output,
            metadata_=trace.metadata,
            started_at=trace.started_at,
            ended_at=trace.ended_at,
            session_id=trace.session_id,
            user_id=trace.user_id,
            tags=trace.tags,
        )
        for span in trace.spans:
            row.spans.append(
                SpanModel(
                    span_id=span.span_id,
                    trace_id=trace.trace_id,
                    parent_span_id=span.parent_span_id,
                    name=span.name,
                    kind=span.kind.value,
                    status=span.status.value,
                    input=span.input,
                    output=span.output,
                    model=span.model,
                    token_usage=span.token_usage,
                    metadata_=span.metadata,
                    started_at=span.started_at,
                    ended_at=span.ended_at,
                    error=span.error,
                    completion_start_time=span.completion_start_time,
                    model_parameters=span.model_parameters,
                )
            )
        self._session.add(row)
        await self._session.flush()
        return trace

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
    ) -> list[Trace]:
        """Return the most recent traces for a project (without spans)."""
        stmt = (
            select(TraceModel)
            .where(TraceModel.project_id == project_id)
            .order_by(TraceModel.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        if session_id is not None:
            stmt = stmt.where(TraceModel.session_id == session_id)
        rows = (await self._session.execute(stmt)).scalars().all()
        return [self._to_trace(r, include_spans=False) for r in rows]

    # -- Session aggregation ---------------------------------------------------

    async def list_sessions(
        self,
        project_id: UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Row[Any]]:
        """Return aggregated session summaries for a project.

        Each row contains: session_id, trace_count, first_trace_at,
        last_trace_at, total_latency_ms, has_error, user_id, tags.
        """
        t = TraceModel.__table__.alias("t")

        stmt = (
            select(
                t.c.session_id,
                func.count(t.c.trace_id).label("trace_count"),
                func.min(t.c.started_at).label("first_trace_at"),
                func.max(t.c.ended_at).label("last_trace_at"),
                func.sum(
                    func.extract("epoch", t.c.ended_at - t.c.started_at) * 1000
                ).label("total_latency_ms"),
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
                        select(
                            func.array_agg(func.distinct(func.unnest(TraceModel.tags)))
                        )
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
            )
            .where(t.c.project_id == project_id, t.c.session_id.isnot(None))
            .group_by(t.c.session_id)
            .order_by(func.max(t.c.created_at).desc())
            .offset(offset)
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return list(result.all())

    async def get_session_traces(
        self,
        project_id: UUID,
        session_id: str,
        limit: int = 200,
        offset: int = 0,
    ) -> list[Trace]:
        """Return all traces for a session in chronological order (without spans)."""
        stmt = (
            select(TraceModel)
            .where(TraceModel.project_id == project_id, TraceModel.session_id == session_id)
            .order_by(TraceModel.started_at.asc())
            .offset(offset)
            .limit(limit)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [self._to_trace(r, include_spans=False) for r in rows]

    # -- Mappers --------------------------------------------------------------

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
            spans=spans,
        )
