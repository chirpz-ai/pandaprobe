"""PostgreSQL implementation of the Trace repository.

Translates between ORM models and pure domain entities for traces
and their child spans.
"""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

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
            org_id=trace.org_id,
            name=trace.name,
            status=trace.status.value,
            input=trace.input,
            output=trace.output,
            metadata_=trace.metadata,
            started_at=trace.started_at,
            ended_at=trace.ended_at,
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
                )
            )
        self._session.add(row)
        await self._session.flush()
        return trace

    async def get_trace(self, trace_id: UUID, org_id: UUID) -> Trace | None:
        """Load a trace with its spans, scoped to an organisation."""
        stmt = (
            select(TraceModel)
            .options(selectinload(TraceModel.spans))
            .where(TraceModel.trace_id == trace_id, TraceModel.org_id == org_id)
        )
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        return self._to_trace(row) if row else None

    async def list_traces(
        self,
        org_id: UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Trace]:
        """Return the most recent traces for an organisation (without spans)."""
        stmt = (
            select(TraceModel)
            .where(TraceModel.org_id == org_id)
            .order_by(TraceModel.created_at.desc())
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
        )

    @classmethod
    def _to_trace(cls, row: TraceModel, *, include_spans: bool = True) -> Trace:
        spans = [cls._to_span(s) for s in row.spans] if include_spans and row.spans else []
        return Trace(
            trace_id=row.trace_id,
            org_id=row.org_id,
            name=row.name,
            status=TraceStatus(row.status),
            input=row.input,
            output=row.output,
            metadata=row.metadata_,
            started_at=row.started_at,
            ended_at=row.ended_at,
            spans=spans,
        )
