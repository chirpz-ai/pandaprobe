"""Unit tests for trace domain entities (no database required)."""

from datetime import datetime, timezone
from uuid import uuid4

from app.core.traces.entities import Span, Trace
from app.registry.constants import SpanKind, SpanStatusCode, TraceStatus


def test_trace_entity_creation() -> None:
    now = datetime.now(timezone.utc)
    trace = Trace(
        trace_id=uuid4(),
        org_id=uuid4(),
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
        org_id=uuid4(),
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
        org_id=uuid4(),
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
