"""Routes for session-based trace aggregation.

Sessions are implicit groupings of traces that share the same
``session_id``.  There is no dedicated ``sessions`` table -- all
data is derived from the ``traces`` table.

Authentication: Bearer JWT (with ``X-Project-ID`` header) **or**
``X-API-Key`` with ``X-Project-Name``.
"""

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.context import ApiContext
from app.api.dependencies import require_project
from app.api.v1.routes.traces import TraceListItem, _trace_to_list_item
from app.infrastructure.db.engine import get_db_session
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


class SessionDetail(SessionSummary):
    """Single session with its ordered traces."""

    traces: list[TraceListItem] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("", response_model=list[SessionSummary])
async def list_sessions(
    ctx: ApiContext = Depends(require_project),
    session: AsyncSession = Depends(get_db_session),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[SessionSummary]:
    """List sessions for the current project.

    Auth: `Bearer` + `X-Project-ID` | `X-API-Key` + `X-Project-Name`
    """
    svc = TraceService(session)
    rows = await svc.list_sessions(ctx.project.id, limit=limit, offset=offset)
    return [
        SessionSummary(
            session_id=r.session_id,
            trace_count=r.trace_count,
            first_trace_at=r.first_trace_at.isoformat(),
            last_trace_at=r.last_trace_at.isoformat() if r.last_trace_at else None,
            total_latency_ms=float(r.total_latency_ms) if r.total_latency_ms is not None else None,
            has_error=r.has_error,
            user_id=r.user_id,
            tags=list(r.tags) if r.tags else [],
        )
        for r in rows
    ]


@router.get("/{session_id}", response_model=SessionDetail)
async def get_session(
    session_id: str,
    ctx: ApiContext = Depends(require_project),
    session: AsyncSession = Depends(get_db_session),
    limit: int = Query(default=200, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
) -> SessionDetail:
    """Retrieve a single session with its traces.

    Auth: `Bearer` + `X-Project-ID` | `X-API-Key` + `X-Project-Name`
    """
    svc = TraceService(session)
    traces = await svc.get_session_traces(
        ctx.project.id, session_id, limit=limit, offset=offset,
    )

    first_trace = traces[0]
    last_trace = traces[-1]

    has_error = any(t.status.value == "ERROR" for t in traces)
    total_ms: float | None = None
    durations = [
        (t.ended_at - t.started_at).total_seconds() * 1000
        for t in traces
        if t.ended_at is not None
    ]
    if durations:
        total_ms = sum(durations)

    all_tags: list[str] = []
    seen_tags: set[str] = set()
    for t in traces:
        for tag in t.tags:
            if tag not in seen_tags:
                seen_tags.add(tag)
                all_tags.append(tag)

    return SessionDetail(
        session_id=session_id,
        trace_count=len(traces),
        first_trace_at=first_trace.started_at.isoformat(),
        last_trace_at=last_trace.ended_at.isoformat() if last_trace.ended_at else None,
        total_latency_ms=total_ms,
        has_error=has_error,
        user_id=first_trace.user_id,
        tags=all_tags,
        traces=[_trace_to_list_item(t) for t in traces],
    )
