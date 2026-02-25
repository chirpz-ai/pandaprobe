"""Unit tests for session-related domain logic and schema construction.

Sessions are implicit groupings of traces sharing a ``session_id``.
These tests verify Pydantic schema construction, the aggregation
helper logic in the route layer, and serialization of session fields.
No database required.
"""

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from app.api.v1.routes.sessions import (
    SessionAnalyticsBucket,
    SessionDeleteResponse,
    SessionDetail,
    SessionSummary,
)
from app.api.v1.routes.traces import TraceListItem
from app.core.traces.entities import Span, Trace
from app.registry.constants import SpanKind, SpanStatusCode, TraceStatus

_UNSET: Any = object()


def _make_trace(
    *,
    session_id: str = "sess-1",
    user_id: str | None = "user-a",
    status: TraceStatus = TraceStatus.COMPLETED,
    tags: list[str] | None = None,
    started_at: datetime | None = None,
    ended_at: Any = _UNSET,
) -> Trace:
    now = started_at or datetime.now(timezone.utc)
    resolved_ended = (now + timedelta(seconds=1)) if ended_at is _UNSET else ended_at
    return Trace(
        trace_id=uuid4(),
        project_id=uuid4(),
        name="test-trace",
        status=status,
        started_at=now,
        ended_at=resolved_ended,
        session_id=session_id,
        user_id=user_id,
        tags=tags or [],
    )


# ---------------------------------------------------------------------------
# Entity-level tests
# ---------------------------------------------------------------------------


def test_trace_entity_preserves_session_fields() -> None:
    """session_id, user_id, tags survive creation and access."""
    trace = _make_trace(
        session_id="conv-42",
        user_id="alice",
        tags=["production", "gpt-4o"],
    )
    assert trace.session_id == "conv-42"
    assert trace.user_id == "alice"
    assert trace.tags == ["production", "gpt-4o"]


def test_session_fields_survive_serialization_roundtrip() -> None:
    """Celery roundtrip: model_dump -> model_validate preserves session fields."""
    trace = _make_trace(session_id="rt-session", user_id="bob", tags=["test"])
    dumped = trace.model_dump(mode="json")
    restored = Trace.model_validate(dumped)

    assert restored.session_id == "rt-session"
    assert restored.user_id == "bob"
    assert restored.tags == ["test"]


# ---------------------------------------------------------------------------
# SessionSummary schema tests
# ---------------------------------------------------------------------------


def test_session_summary_schema_construction() -> None:
    summary = SessionSummary(
        session_id="sess-1",
        trace_count=5,
        first_trace_at="2026-01-01T00:00:00+00:00",
        last_trace_at="2026-01-01T00:05:00+00:00",
        total_latency_ms=3200.0,
        has_error=False,
        user_id="user-a",
        tags=["prod", "agent-v2"],
        total_span_count=12,
        total_tokens=500,
        total_cost=0.042,
    )
    assert summary.session_id == "sess-1"
    assert summary.trace_count == 5
    assert summary.has_error is False
    assert len(summary.tags) == 2
    assert summary.total_span_count == 12
    assert summary.total_tokens == 500
    assert summary.total_cost == 0.042


def test_session_summary_nullable_fields() -> None:
    """last_trace_at, total_latency_ms, and user_id can all be None."""
    summary = SessionSummary(
        session_id="s",
        trace_count=1,
        first_trace_at="2026-01-01T00:00:00+00:00",
        last_trace_at=None,
        total_latency_ms=None,
        has_error=False,
        user_id=None,
        tags=[],
    )
    assert summary.last_trace_at is None
    assert summary.total_latency_ms is None
    assert summary.user_id is None
    assert summary.total_span_count == 0
    assert summary.total_tokens == 0
    assert summary.total_cost == 0.0


def test_session_summary_span_stats_defaults() -> None:
    """Span stat fields default to zero when omitted."""
    summary = SessionSummary(
        session_id="x",
        trace_count=1,
        first_trace_at="2026-01-01T00:00:00+00:00",
        last_trace_at=None,
        total_latency_ms=None,
        has_error=False,
        user_id=None,
        tags=[],
    )
    assert summary.total_span_count == 0
    assert summary.total_tokens == 0
    assert summary.total_cost == 0.0


# ---------------------------------------------------------------------------
# SessionDetail schema tests
# ---------------------------------------------------------------------------


def test_session_detail_includes_traces_and_io() -> None:
    trace_item = TraceListItem(
        trace_id=uuid4(),
        name="t1",
        status=TraceStatus.COMPLETED,
        started_at="2026-01-01T00:00:00+00:00",
        ended_at="2026-01-01T00:00:01+00:00",
        session_id="sess-1",
        user_id="user-a",
        tags=["tag1"],
        latency_ms=1000.0,
        span_count=3,
        total_tokens=100,
        total_cost=0.005,
    )
    detail = SessionDetail(
        session_id="sess-1",
        trace_count=1,
        first_trace_at="2026-01-01T00:00:00+00:00",
        last_trace_at="2026-01-01T00:00:01+00:00",
        total_latency_ms=1000.0,
        has_error=False,
        user_id="user-a",
        tags=["tag1"],
        total_span_count=3,
        total_tokens=100,
        total_cost=0.005,
        input={"prompt": "hello"},
        output={"response": "world"},
        traces=[trace_item],
    )
    assert len(detail.traces) == 1
    assert detail.traces[0].span_count == 3
    assert detail.input == {"prompt": "hello"}
    assert detail.output == {"response": "world"}


def test_session_detail_io_nullable() -> None:
    """input/output default to None."""
    detail = SessionDetail(
        session_id="s",
        trace_count=0,
        first_trace_at="2026-01-01T00:00:00+00:00",
        last_trace_at=None,
        total_latency_ms=None,
        has_error=False,
        user_id=None,
        tags=[],
    )
    assert detail.input is None
    assert detail.output is None
    assert detail.traces == []


# ---------------------------------------------------------------------------
# SessionDeleteResponse schema test
# ---------------------------------------------------------------------------


def test_session_delete_response() -> None:
    resp = SessionDeleteResponse(deleted=5)
    assert resp.deleted == 5


# ---------------------------------------------------------------------------
# SessionAnalyticsBucket schema tests
# ---------------------------------------------------------------------------


def test_session_analytics_bucket_construction() -> None:
    bucket = SessionAnalyticsBucket(
        bucket="2026-01-01T00:00:00+00:00",
        session_count=10,
        avg_traces_per_session=3.5,
        avg_session_duration_ms=4200.0,
    )
    assert bucket.session_count == 10
    assert bucket.avg_traces_per_session == 3.5
    assert bucket.avg_session_duration_ms == 4200.0


def test_session_analytics_bucket_defaults() -> None:
    bucket = SessionAnalyticsBucket(bucket="2026-01-01T00:00:00+00:00")
    assert bucket.session_count == 0
    assert bucket.avg_traces_per_session is None
    assert bucket.avg_session_duration_ms is None


# ---------------------------------------------------------------------------
# Helper logic tests (still valid — reproduced from route-layer patterns)
# ---------------------------------------------------------------------------


def test_session_tag_deduplication_logic() -> None:
    """Reproduce the tag deduplication logic from get_session route."""
    traces = [
        _make_trace(tags=["a", "b"]),
        _make_trace(tags=["b", "c"]),
        _make_trace(tags=["a", "c", "d"]),
    ]

    all_tags: list[str] = []
    seen: set[str] = set()
    for t in traces:
        for tag in t.tags:
            if tag not in seen:
                seen.add(tag)
                all_tags.append(tag)

    assert all_tags == ["a", "b", "c", "d"]


def test_session_error_detection_logic() -> None:
    """has_error should be True if any trace has ERROR status."""
    traces = [
        _make_trace(status=TraceStatus.COMPLETED),
        _make_trace(status=TraceStatus.ERROR),
        _make_trace(status=TraceStatus.COMPLETED),
    ]
    has_error = any(t.status.value == "ERROR" for t in traces)
    assert has_error is True


def test_session_no_error_detection() -> None:
    traces = [
        _make_trace(status=TraceStatus.COMPLETED),
        _make_trace(status=TraceStatus.COMPLETED),
    ]
    has_error = any(t.status.value == "ERROR" for t in traces)
    assert has_error is False


def test_session_latency_computation() -> None:
    """Total latency is the sum of all trace durations."""
    now = datetime.now(timezone.utc)
    traces = [
        _make_trace(started_at=now, ended_at=now + timedelta(milliseconds=500)),
        _make_trace(started_at=now, ended_at=now + timedelta(milliseconds=1500)),
        _make_trace(started_at=now, ended_at=None),  # incomplete trace
    ]

    durations = [(t.ended_at - t.started_at).total_seconds() * 1000 for t in traces if t.ended_at is not None]
    total_ms = sum(durations) if durations else None

    assert total_ms == 2000.0


def test_session_latency_all_incomplete() -> None:
    """When no trace has ended_at, latency should be None."""
    traces = [
        _make_trace(ended_at=None),
        _make_trace(ended_at=None),
    ]

    durations = [(t.ended_at - t.started_at).total_seconds() * 1000 for t in traces if t.ended_at is not None]
    total_ms = sum(durations) if durations else None

    assert total_ms is None


def test_span_with_session_trace_roundtrip() -> None:
    """Ensure a trace with session_id + spans survives Celery serialization."""
    now = datetime.now(timezone.utc)
    trace = Trace(
        trace_id=uuid4(),
        project_id=uuid4(),
        name="session-trace",
        status=TraceStatus.COMPLETED,
        started_at=now,
        ended_at=now + timedelta(seconds=2),
        session_id="chat-session-99",
        user_id="end-user-1",
        tags=["production"],
        spans=[
            Span(
                span_id=uuid4(),
                trace_id=uuid4(),
                name="llm-call",
                kind=SpanKind.LLM,
                status=SpanStatusCode.OK,
                started_at=now,
                ended_at=now + timedelta(seconds=1),
                model="gpt-4o",
                token_usage={"prompt_tokens": 100, "completion_tokens": 50},
                error=None,
                completion_start_time=now + timedelta(milliseconds=200),
                model_parameters={"temperature": 0.7, "max_tokens": 1024},
                cost={"input": 0.0025, "output": 0.0045, "total": 0.007},
            ),
        ],
    )

    dumped = trace.model_dump(mode="json")
    restored = Trace.model_validate(dumped)

    assert restored.session_id == "chat-session-99"
    assert restored.user_id == "end-user-1"
    assert restored.spans[0].model == "gpt-4o"
    assert restored.spans[0].cost["total"] == 0.007
    assert restored.spans[0].completion_start_time is not None
    assert restored.spans[0].model_parameters["temperature"] == 0.7
