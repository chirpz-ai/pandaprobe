"""Integration tests for span CRUD operations."""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from httpx import AsyncClient

from .factories import build_span_payload


async def test_get_trace_with_spans_returns_span_fields(client: AsyncClient, seed_trace) -> None:
    now = datetime.now(timezone.utc)
    span = build_span_payload(
        name="llm-call",
        kind="LLM",
        status="OK",
        model="gpt-4o",
        started_at=now - timedelta(seconds=1),
        ended_at=now,
        token_usage={"prompt_tokens": 10, "completion_tokens": 5},
        cost={"total": 0.005},
    )
    trace = await seed_trace(name="span-test", spans=[span])

    resp = await client.get(f"/traces/{trace.trace_id}")
    assert resp.status_code == 200
    spans = resp.json()["spans"]
    assert len(spans) == 1
    s = spans[0]
    assert s["name"] == "llm-call"
    assert s["kind"] == "LLM"
    assert s["model"] == "gpt-4o"
    assert s["token_usage"]["prompt_tokens"] == 10


async def test_span_latency_ms_computed(client: AsyncClient, seed_trace) -> None:
    now = datetime.now(timezone.utc)
    span = build_span_payload(
        started_at=now - timedelta(milliseconds=1234),
        ended_at=now,
    )
    trace = await seed_trace(spans=[span])

    resp = await client.get(f"/traces/{trace.trace_id}")
    s = resp.json()["spans"][0]
    assert s["latency_ms"] is not None
    assert abs(s["latency_ms"] - 1234.0) < 5.0


async def test_span_ttft_computed(client: AsyncClient, seed_trace) -> None:
    now = datetime.now(timezone.utc)
    started = now - timedelta(seconds=1)
    span = build_span_payload(
        started_at=started,
        ended_at=now,
        completion_start_time=started + timedelta(milliseconds=350),
    )
    trace = await seed_trace(spans=[span])

    resp = await client.get(f"/traces/{trace.trace_id}")
    s = resp.json()["spans"][0]
    assert s["time_to_first_token_ms"] is not None
    assert abs(s["time_to_first_token_ms"] - 350.0) < 5.0


async def test_span_ttft_none_when_no_completion_start(client: AsyncClient, seed_trace) -> None:
    span = build_span_payload(completion_start_time=None)
    trace = await seed_trace(spans=[span])

    resp = await client.get(f"/traces/{trace.trace_id}")
    s = resp.json()["spans"][0]
    assert s["time_to_first_token_ms"] is None


async def test_add_spans_to_existing_trace(client: AsyncClient, seed_trace) -> None:
    trace = await seed_trace(name="expandable")
    now = datetime.now(timezone.utc)
    new_spans = [
        {
            "span_id": str(uuid4()),
            "name": "added-span-1",
            "kind": "TOOL",
            "status": "OK",
            "started_at": (now - timedelta(seconds=1)).isoformat(),
            "ended_at": now.isoformat(),
        },
        {
            "span_id": str(uuid4()),
            "name": "added-span-2",
            "kind": "LLM",
            "status": "OK",
            "started_at": (now - timedelta(seconds=1)).isoformat(),
            "ended_at": now.isoformat(),
        },
    ]
    resp = await client.post(f"/traces/{trace.trace_id}/spans", json=new_spans)
    assert resp.status_code == 201
    body = resp.json()
    assert len(body["span_ids"]) == 2

    detail = await client.get(f"/traces/{trace.trace_id}")
    assert len(detail.json()["spans"]) == 2


async def test_update_span(client: AsyncClient, seed_trace) -> None:
    span = build_span_payload(name="original-span", kind="LLM")
    trace = await seed_trace(spans=[span])

    span_id = trace.spans[0].span_id
    resp = await client.patch(
        f"/traces/{trace.trace_id}/spans/{span_id}",
        json={"name": "updated-span", "model": "claude-3"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "updated-span"
    assert body["model"] == "claude-3"


async def test_add_spans_to_nonexistent_trace_returns_404(client: AsyncClient) -> None:
    now = datetime.now(timezone.utc)
    spans = [
        {
            "span_id": str(uuid4()),
            "name": "orphan",
            "started_at": now.isoformat(),
        },
    ]
    resp = await client.post(f"/traces/{uuid4()}/spans", json=spans)
    assert resp.status_code == 404
