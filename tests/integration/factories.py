"""Test data builders for integration tests.

Each function returns a plain dict suitable for constructing domain entities
via ``Trace.model_validate`` or for JSON submission to API endpoints
(timestamps are kept as ``datetime`` objects — callers serialise to ISO
strings when posting to the API).
"""

from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4


def build_trace_payload(**overrides) -> dict:
    """Return a dict matching the ``TraceCreate`` schema with sensible defaults.

    Every field can be overridden via keyword arguments.  Timestamps are
    ``datetime`` objects; callers should call ``.isoformat()`` when building
    JSON request bodies.
    """
    now = datetime.now(timezone.utc)
    defaults: dict = {
        "trace_id": uuid4(),
        "name": "test-trace",
        "status": "COMPLETED",
        "input": None,
        "output": None,
        "metadata": {},
        "started_at": now - timedelta(seconds=1),
        "ended_at": now,
        "session_id": None,
        "user_id": None,
        "tags": [],
        "environment": None,
        "release": None,
        "spans": [],
    }
    defaults.update(overrides)
    return defaults


def build_span_payload(**overrides) -> dict:
    """Return a dict matching the ``SpanCreate`` schema with sensible defaults."""
    now = datetime.now(timezone.utc)
    defaults: dict = {
        "span_id": uuid4(),
        "parent_span_id": None,
        "name": "test-span",
        "kind": "LLM",
        "status": "OK",
        "input": None,
        "output": None,
        "model": None,
        "token_usage": None,
        "metadata": {},
        "started_at": now - timedelta(milliseconds=500),
        "ended_at": now,
        "error": None,
        "completion_start_time": None,
        "model_parameters": None,
        "cost": None,
    }
    defaults.update(overrides)
    return defaults


def build_trace_with_spans(span_count: int = 3, **overrides) -> dict:
    """Return a trace payload with *span_count* properly-chained spans.

    The first span is the root (no parent); subsequent spans reference
    the previous span as their parent.
    """
    now = datetime.now(timezone.utc)
    trace_id = overrides.pop("trace_id", uuid4())
    spans = []
    prev_span_id = None
    for i in range(span_count):
        started = now - timedelta(milliseconds=500 * (span_count - i))
        ended = started + timedelta(milliseconds=400)
        span = build_span_payload(
            span_id=uuid4(),
            parent_span_id=prev_span_id,
            name=f"span-{i}",
            kind="LLM" if i % 2 == 0 else "TOOL",
            started_at=started,
            ended_at=ended,
            model="gpt-4o" if i % 2 == 0 else None,
            token_usage={"prompt_tokens": 10, "completion_tokens": 5} if i % 2 == 0 else None,
            cost={"input": 0.001, "output": 0.002, "total": 0.003} if i % 2 == 0 else None,
        )
        spans.append(span)
        prev_span_id = span["span_id"]

    return build_trace_payload(trace_id=trace_id, spans=spans, **overrides)


def build_session_traces(session_id: str, count: int = 3, **overrides) -> list[dict]:
    """Return *count* trace payloads sharing the same ``session_id``.

    Traces are spread across a time range so ordering tests work.
    """
    base_time = datetime.now(timezone.utc) - timedelta(hours=count)
    traces = []
    for i in range(count):
        started = base_time + timedelta(hours=i)
        ended = started + timedelta(seconds=2)
        trace = build_trace_payload(
            session_id=session_id,
            name=f"session-trace-{i}",
            started_at=started,
            ended_at=ended,
            **overrides,
        )
        traces.append(trace)
    return traces


def _serialize_payload(payload: dict) -> dict:
    """Convert a factory payload dict to JSON-ready format for API submission."""
    result = dict(payload)
    if isinstance(result.get("trace_id"), UUID):
        result["trace_id"] = str(result["trace_id"])
    if isinstance(result.get("started_at"), datetime):
        result["started_at"] = result["started_at"].isoformat()
    if isinstance(result.get("ended_at"), datetime):
        result["ended_at"] = result["ended_at"].isoformat()
    for span in result.get("spans", []):
        if isinstance(span.get("span_id"), UUID):
            span["span_id"] = str(span["span_id"])
        if isinstance(span.get("parent_span_id"), UUID):
            span["parent_span_id"] = str(span["parent_span_id"])
        if isinstance(span.get("started_at"), datetime):
            span["started_at"] = span["started_at"].isoformat()
        if isinstance(span.get("ended_at"), datetime):
            span["ended_at"] = span["ended_at"].isoformat()
        if isinstance(span.get("completion_start_time"), datetime):
            span["completion_start_time"] = span["completion_start_time"].isoformat()
    return result
