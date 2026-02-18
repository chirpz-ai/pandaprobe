"""Routes for trace ingestion and retrieval.

``POST /traces`` accepts the universal Opentracer format, validates
the schema, resolves the project from the API key, and enqueues the
trace for background persistence.
"""

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies import APIKeyContext, require_api_key
from app.core.traces.entities import Span, Trace
from app.infrastructure.db.engine import get_db_session
from app.registry.constants import SpanKind, SpanStatusCode, TraceStatus
from app.services.trace_service import TraceService

router = APIRouter(prefix="/traces", tags=["traces"])


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------


class SpanCreate(BaseModel):
    """Schema for a span inside a trace-ingestion request."""

    span_id: UUID = Field(default_factory=uuid4)
    parent_span_id: UUID | None = None
    name: str = Field(min_length=1, max_length=512)
    kind: SpanKind = SpanKind.OTHER
    status: SpanStatusCode = SpanStatusCode.UNSET
    input: Any | None = None
    output: Any | None = None
    model: str | None = None
    token_usage: dict[str, int] | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    started_at: datetime
    ended_at: datetime | None = None


class TraceCreate(BaseModel):
    """Schema for the ``POST /traces`` request body."""

    trace_id: UUID = Field(default_factory=uuid4)
    name: str = Field(min_length=1, max_length=512)
    status: TraceStatus = TraceStatus.COMPLETED
    input: Any | None = None
    output: Any | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    started_at: datetime
    ended_at: datetime | None = None
    spans: list[SpanCreate] = Field(default_factory=list)


class TraceAccepted(BaseModel):
    """Response body for a successfully enqueued trace."""

    trace_id: UUID
    task_id: str


class SpanResponse(BaseModel):
    """Public span representation."""

    span_id: UUID
    trace_id: UUID
    parent_span_id: UUID | None
    name: str
    kind: SpanKind
    status: SpanStatusCode
    input: Any | None
    output: Any | None
    model: str | None
    token_usage: dict[str, int] | None
    metadata: dict[str, Any]
    started_at: str
    ended_at: str | None


class TraceResponse(BaseModel):
    """Public trace representation (single-item detail)."""

    trace_id: UUID
    project_id: UUID
    name: str
    status: TraceStatus
    input: Any | None
    output: Any | None
    metadata: dict[str, Any]
    started_at: str
    ended_at: str | None
    spans: list[SpanResponse] = Field(default_factory=list)


class TraceListItem(BaseModel):
    """Lightweight trace summary used in list responses."""

    trace_id: UUID
    name: str
    status: TraceStatus
    started_at: str
    ended_at: str | None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("", status_code=202, response_model=TraceAccepted)
async def ingest_trace(
    body: TraceCreate,
    ctx: APIKeyContext = Depends(require_api_key),
) -> TraceAccepted:
    """Accept a trace payload for asynchronous persistence.

    The project is resolved automatically from the API key.
    """
    trace = Trace(
        trace_id=body.trace_id,
        project_id=ctx.project_id,
        name=body.name,
        status=body.status,
        input=body.input,
        output=body.output,
        metadata=body.metadata,
        started_at=body.started_at,
        ended_at=body.ended_at,
        spans=[
            Span(
                span_id=s.span_id,
                trace_id=body.trace_id,
                parent_span_id=s.parent_span_id,
                name=s.name,
                kind=s.kind,
                status=s.status,
                input=s.input,
                output=s.output,
                model=s.model,
                token_usage=s.token_usage,
                metadata=s.metadata,
                started_at=s.started_at,
                ended_at=s.ended_at,
            )
            for s in body.spans
        ],
    )

    task_id = TraceService.enqueue_trace(trace)
    return TraceAccepted(trace_id=trace.trace_id, task_id=task_id)


@router.get("/{trace_id}", response_model=TraceResponse)
async def get_trace(
    trace_id: UUID,
    ctx: APIKeyContext = Depends(require_api_key),
    session: AsyncSession = Depends(get_db_session),
) -> TraceResponse:
    """Retrieve a single trace with all its spans."""
    svc = TraceService(session)
    trace = await svc.get_trace(trace_id, ctx.project_id)
    return _trace_to_response(trace)


@router.get("", response_model=list[TraceListItem])
async def list_traces(
    ctx: APIKeyContext = Depends(require_api_key),
    session: AsyncSession = Depends(get_db_session),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[TraceListItem]:
    """List traces for the project associated with the API key."""
    svc = TraceService(session)
    traces = await svc.list_traces(ctx.project_id, limit=limit, offset=offset)
    return [
        TraceListItem(
            trace_id=t.trace_id,
            name=t.name,
            status=t.status,
            started_at=t.started_at.isoformat(),
            ended_at=t.ended_at.isoformat() if t.ended_at else None,
        )
        for t in traces
    ]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _trace_to_response(trace: Trace) -> TraceResponse:
    return TraceResponse(
        trace_id=trace.trace_id,
        project_id=trace.project_id,
        name=trace.name,
        status=trace.status,
        input=trace.input,
        output=trace.output,
        metadata=trace.metadata,
        started_at=trace.started_at.isoformat(),
        ended_at=trace.ended_at.isoformat() if trace.ended_at else None,
        spans=[
            SpanResponse(
                span_id=s.span_id,
                trace_id=s.trace_id,
                parent_span_id=s.parent_span_id,
                name=s.name,
                kind=s.kind,
                status=s.status,
                input=s.input,
                output=s.output,
                model=s.model,
                token_usage=s.token_usage,
                metadata=s.metadata,
                started_at=s.started_at.isoformat(),
                ended_at=s.ended_at.isoformat() if s.ended_at else None,
            )
            for s in trace.spans
        ],
    )
