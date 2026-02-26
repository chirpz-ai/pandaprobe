"""Routes for session-based trace aggregation.

Sessions are implicit groupings of traces that share the same
``session_id``.  There is no dedicated ``sessions`` table -- all
data is derived from the ``traces`` table.

Authentication: Bearer JWT (with ``X-Project-ID`` header) **or**
``X-API-Key`` with ``X-Project-Name``.
"""

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.context import ApiContext
from app.api.dependencies import require_project
from app.api.v1.routes.traces import TraceListItem, _row_to_list_item
from app.api.v1.schemas import PaginatedResponse
from app.infrastructure.db.engine import get_db_session
from app.registry.constants import (
    AnalyticsGranularity,
    SessionSortBy,
    SortOrder,
)
from app.services.trace_service import TraceService

router = APIRouter(prefix="/sessions", tags=["sessions"])


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class SessionSummary(BaseModel):
    """Aggregated summary for a session."""

    session_id: str
    trace_count: int
    first_trace_at: str
    last_trace_at: str | None
    total_latency_ms: float | None
    has_error: bool
    user_id: str | None
    tags: list[str]
    total_span_count: int = 0
    total_tokens: int = 0
    total_cost: float = 0.0


class SessionDetail(SessionSummary):
    """Single session with its ordered traces and I/O."""

    input: Any | None = None
    output: Any | None = None
    traces: list[TraceListItem] = Field(default_factory=list)


class SessionDeleteResponse(BaseModel):
    """Response for session deletion (count of traces removed)."""

    deleted: int


class SessionAnalyticsBucket(BaseModel):
    """Time-bucketed session statistics."""

    bucket: str
    session_count: int = 0
    avg_traces_per_session: float | None = None
    avg_session_duration_ms: float | None = None


# ---------------------------------------------------------------------------
# Endpoints — static paths first
# ---------------------------------------------------------------------------


@router.get("", response_model=PaginatedResponse[SessionSummary])
async def list_sessions(
    ctx: ApiContext = Depends(require_project),
    session: AsyncSession = Depends(get_db_session),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    user_id: str | None = Query(default=None),
    has_error: bool | None = Query(default=None),
    started_after: datetime | None = Query(default=None),
    started_before: datetime | None = Query(default=None),
    tags: list[str] | None = Query(default=None),
    query: str | None = Query(default=None, description="ILIKE filter on session_id"),
    sort_by: SessionSortBy = Query(default=SessionSortBy.RECENT),
    sort_order: SortOrder = Query(default=SortOrder.DESC),
) -> PaginatedResponse[SessionSummary]:
    """List sessions for the current project.

    Auth: `Bearer` + `X-Project-ID` | `X-API-Key` + `X-Project-Name`
    """
    svc = TraceService(session)
    rows, total = await svc.list_sessions(
        ctx.project.id,
        limit=limit,
        offset=offset,
        user_id=user_id,
        has_error=has_error,
        started_after=started_after,
        started_before=started_before,
        tags=tags,
        query=query,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    items = [_row_to_session_summary(r) for r in rows]
    return PaginatedResponse(items=items, total=total, limit=limit, offset=offset)


@router.get("/analytics", response_model=list[SessionAnalyticsBucket])
async def get_session_analytics(
    ctx: ApiContext = Depends(require_project),
    session: AsyncSession = Depends(get_db_session),
    granularity: AnalyticsGranularity = Query(default=AnalyticsGranularity.DAY),
    started_after: datetime = Query(...),
    started_before: datetime = Query(...),
) -> list[SessionAnalyticsBucket]:
    """Time-series session statistics.

    Auth: `Bearer` + `X-Project-ID` | `X-API-Key` + `X-Project-Name`
    """
    svc = TraceService(session)
    rows = await svc.get_session_analytics(
        ctx.project.id,
        granularity,
        started_after,
        started_before,
    )
    return [
        SessionAnalyticsBucket(
            bucket=r.bucket.isoformat() if r.bucket else "",
            session_count=r.session_count or 0,
            avg_traces_per_session=float(r.avg_traces_per_session) if r.avg_traces_per_session is not None else None,
            avg_session_duration_ms=float(r.avg_session_duration_ms) if r.avg_session_duration_ms is not None else None,
        )
        for r in rows
    ]


# ---------------------------------------------------------------------------
# Parameterised /{session_id} routes
# ---------------------------------------------------------------------------


@router.get("/{session_id}", response_model=SessionDetail)
async def get_session(
    session_id: str,
    ctx: ApiContext = Depends(require_project),
    session: AsyncSession = Depends(get_db_session),
    limit: int = Query(default=200, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
) -> SessionDetail:
    """Retrieve a single session with its traces (including span stats).

    Summary fields (trace_count, latency, error, tags, tokens, cost)
    are computed via SQL aggregation over *all* traces in the session,
    regardless of the pagination window.

    Auth: `Bearer` + `X-Project-ID` | `X-API-Key` + `X-Project-Name`
    """
    svc = TraceService(session)
    summary = await svc.get_session_summary(ctx.project.id, session_id)
    trace_rows, _total = await svc.list_session_traces_with_stats(
        ctx.project.id,
        session_id,
        limit=limit,
        offset=offset,
    )

    return SessionDetail(
        session_id=summary.session_id,
        trace_count=summary.trace_count,
        first_trace_at=summary.first_trace_at.isoformat(),
        last_trace_at=summary.last_trace_at.isoformat() if summary.last_trace_at else None,
        total_latency_ms=float(summary.total_latency_ms) if summary.total_latency_ms is not None else None,
        has_error=summary.has_error,
        user_id=summary.user_id,
        tags=list(summary.tags) if summary.tags else [],
        total_span_count=int(summary.total_span_count) if summary.total_span_count is not None else 0,
        total_tokens=int(summary.total_tokens) if summary.total_tokens is not None else 0,
        total_cost=float(summary.total_cost) if summary.total_cost is not None else 0.0,
        input=summary.input,
        output=summary.output,
        traces=[_row_to_list_item(r) for r in trace_rows],
    )


@router.delete("/{session_id}", response_model=SessionDeleteResponse)
async def delete_session(
    session_id: str,
    ctx: ApiContext = Depends(require_project),
    session: AsyncSession = Depends(get_db_session),
) -> SessionDeleteResponse:
    """Delete all traces (and cascaded spans) for a session.

    Auth: `Bearer` + `X-Project-ID` | `X-API-Key` + `X-Project-Name`
    """
    svc = TraceService(session)
    count = await svc.delete_session(ctx.project.id, session_id)
    return SessionDeleteResponse(deleted=count)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _row_to_session_summary(r: Any) -> SessionSummary:
    return SessionSummary(
        session_id=r.session_id,
        trace_count=r.trace_count,
        first_trace_at=r.first_trace_at.isoformat(),
        last_trace_at=r.last_trace_at.isoformat() if r.last_trace_at else None,
        total_latency_ms=float(r.total_latency_ms) if r.total_latency_ms is not None else None,
        has_error=r.has_error,
        user_id=r.user_id,
        tags=list(r.tags) if r.tags else [],
        total_span_count=int(r.total_span_count) if r.total_span_count is not None else 0,
        total_tokens=int(r.total_tokens) if r.total_tokens is not None else 0,
        total_cost=float(r.total_cost) if r.total_cost is not None else 0.0,
    )
