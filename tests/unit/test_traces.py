"""Unit tests for trace domain entities (no database required)."""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.api.v1.routes.traces import SpanResponse, _span_to_response
from app.core.traces.entities import Span, Trace
from app.registry.constants import SpanKind, SpanStatusCode, TraceStatus


def test_trace_entity_creation() -> None:
    now = datetime.now(timezone.utc)
    trace = Trace(
        trace_id=uuid4(),
        project_id=uuid4(),
        name="test-agent-run",
        status=TraceStatus.COMPLETED,
        started_at=now,
        ended_at=now,
    )
    assert trace.name == "test-agent-run"
    assert trace.status == TraceStatus.COMPLETED
    assert trace.spans == []


def test_trace_with_nested_spans() -> None:
    now = datetime.now(timezone.utc)
    trace_id = uuid4()
    root_span_id = uuid4()

    root_span = Span(
        span_id=root_span_id,
        trace_id=trace_id,
        name="agent",
        kind=SpanKind.AGENT,
        status=SpanStatusCode.OK,
        started_at=now,
        ended_at=now,
    )
    child_span = Span(
        span_id=uuid4(),
        trace_id=trace_id,
        parent_span_id=root_span_id,
        name="llm-call",
        kind=SpanKind.LLM,
        status=SpanStatusCode.OK,
        input={"prompt": "hello"},
        output={"text": "world"},
        model="gpt-4o",
        token_usage={"prompt_tokens": 5, "completion_tokens": 3},
        started_at=now,
        ended_at=now,
    )

    trace = Trace(
        trace_id=trace_id,
        project_id=uuid4(),
        name="nested-trace",
        status=TraceStatus.COMPLETED,
        started_at=now,
        ended_at=now,
        spans=[root_span, child_span],
    )

    assert len(trace.spans) == 2
    assert trace.spans[0].kind == SpanKind.AGENT
    assert trace.spans[1].parent_span_id == root_span_id
    assert trace.spans[1].token_usage["completion_tokens"] == 3


def test_trace_serialization_roundtrip() -> None:
    """Ensure a trace survives JSON serialisation (used by Celery)."""
    now = datetime.now(timezone.utc)
    trace = Trace(
        trace_id=uuid4(),
        project_id=uuid4(),
        name="roundtrip-test",
        status=TraceStatus.COMPLETED,
        started_at=now,
        spans=[
            Span(
                span_id=uuid4(),
                trace_id=uuid4(),
                name="tool-call",
                kind=SpanKind.TOOL,
                status=SpanStatusCode.OK,
                started_at=now,
                metadata={"key": "value"},
            )
        ],
    )

    dumped = trace.model_dump(mode="json")
    restored = Trace.model_validate(dumped)

    assert restored.trace_id == trace.trace_id
    assert restored.spans[0].kind == SpanKind.TOOL
    assert restored.spans[0].metadata == {"key": "value"}


def test_trace_environment_and_release_fields() -> None:
    """Environment and release are optional string fields on Trace."""
    now = datetime.now(timezone.utc)
    trace = Trace(
        trace_id=uuid4(),
        project_id=uuid4(),
        name="env-release-test",
        status=TraceStatus.COMPLETED,
        started_at=now,
        environment="production",
        release="v1.2.3",
    )
    assert trace.environment == "production"
    assert trace.release == "v1.2.3"


def test_trace_environment_and_release_defaults_to_none() -> None:
    now = datetime.now(timezone.utc)
    trace = Trace(
        trace_id=uuid4(),
        project_id=uuid4(),
        name="defaults",
        status=TraceStatus.COMPLETED,
        started_at=now,
    )
    assert trace.environment is None
    assert trace.release is None


def test_trace_environment_release_serialization_roundtrip() -> None:
    now = datetime.now(timezone.utc)
    trace = Trace(
        trace_id=uuid4(),
        project_id=uuid4(),
        name="roundtrip",
        status=TraceStatus.COMPLETED,
        started_at=now,
        environment="staging",
        release="abc123",
    )
    dumped = trace.model_dump(mode="json")
    restored = Trace.model_validate(dumped)
    assert restored.environment == "staging"
    assert restored.release == "abc123"


def test_span_response_latency_ms_computed() -> None:
    """latency_ms is computed from started_at and ended_at."""
    now = datetime.now(timezone.utc)
    span = Span(
        span_id=uuid4(),
        trace_id=uuid4(),
        name="llm",
        kind=SpanKind.LLM,
        status=SpanStatusCode.OK,
        started_at=now,
        ended_at=now + timedelta(milliseconds=1234),
    )
    resp = _span_to_response(span)
    assert resp.latency_ms is not None
    assert abs(resp.latency_ms - 1234.0) < 1.0


def test_span_response_latency_ms_none_when_no_ended_at() -> None:
    now = datetime.now(timezone.utc)
    span = Span(
        span_id=uuid4(),
        trace_id=uuid4(),
        name="llm",
        kind=SpanKind.LLM,
        status=SpanStatusCode.OK,
        started_at=now,
        ended_at=None,
    )
    resp = _span_to_response(span)
    assert resp.latency_ms is None


def test_span_response_time_to_first_token_ms_computed() -> None:
    """time_to_first_token_ms is computed from started_at and completion_start_time."""
    now = datetime.now(timezone.utc)
    span = Span(
        span_id=uuid4(),
        trace_id=uuid4(),
        name="llm-stream",
        kind=SpanKind.LLM,
        status=SpanStatusCode.OK,
        started_at=now,
        ended_at=now + timedelta(seconds=2),
        completion_start_time=now + timedelta(milliseconds=350),
    )
    resp = _span_to_response(span)
    assert resp.time_to_first_token_ms is not None
    assert abs(resp.time_to_first_token_ms - 350.0) < 1.0


def test_span_response_time_to_first_token_ms_none_when_no_completion_start() -> None:
    now = datetime.now(timezone.utc)
    span = Span(
        span_id=uuid4(),
        trace_id=uuid4(),
        name="tool",
        kind=SpanKind.TOOL,
        status=SpanStatusCode.OK,
        started_at=now,
        ended_at=now + timedelta(seconds=1),
    )
    resp = _span_to_response(span)
    assert resp.time_to_first_token_ms is None
