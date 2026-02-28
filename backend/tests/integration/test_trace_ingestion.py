"""Integration tests for end-to-end trace ingestion (POST /traces).

With ``nest_asyncio`` and Celery eager mode, ``POST /traces`` runs the
full pipeline: FastAPI handler -> ``TraceService.enqueue_trace`` ->
``process_trace`` Celery task -> ``_persist_trace`` -> PostgreSQL commit.
The trace is then retrievable via ``GET /traces/{trace_id}``.
"""

from uuid import uuid4

from httpx import AsyncClient

from .factories import _serialize_payload, build_span_payload, build_trace_payload, build_trace_with_spans


async def test_post_then_get_roundtrip(client: AsyncClient) -> None:
    """POST a trace through Celery eager mode, then GET it back."""
    payload = _serialize_payload(build_trace_payload(name="e2e-roundtrip"))
    resp = await client.post("/traces", json=payload)
    assert resp.status_code == 202
    body = resp.json()
    trace_id = body["trace_id"]
    assert "task_id" in body

    detail = await client.get(f"/traces/{trace_id}")
    assert detail.status_code == 200
    data = detail.json()
    assert data["name"] == "e2e-roundtrip"
    assert data["trace_id"] == trace_id


async def test_post_trace_with_spans_roundtrip(client: AsyncClient) -> None:
    """POST a trace with spans, then verify spans are persisted."""
    payload = _serialize_payload(build_trace_with_spans(span_count=3, name="with-spans"))
    resp = await client.post("/traces", json=payload)
    assert resp.status_code == 202
    trace_id = resp.json()["trace_id"]

    detail = await client.get(f"/traces/{trace_id}")
    assert detail.status_code == 200
    data = detail.json()
    assert len(data["spans"]) == 3
    for span in data["spans"]:
        assert span["latency_ms"] is not None


async def test_post_same_trace_id_twice_upserts(client: AsyncClient) -> None:
    """Posting the same trace_id twice updates the trace, not duplicates it."""
    trace_id = uuid4()
    payload1 = _serialize_payload(build_trace_payload(trace_id=trace_id, name="version-1"))
    payload2 = _serialize_payload(build_trace_payload(trace_id=trace_id, name="version-2"))

    resp1 = await client.post("/traces", json=payload1)
    assert resp1.status_code == 202

    resp2 = await client.post("/traces", json=payload2)
    assert resp2.status_code == 202

    detail = await client.get(f"/traces/{trace_id}")
    assert detail.status_code == 200
    assert detail.json()["name"] == "version-2"


async def test_post_trace_returns_202(client: AsyncClient) -> None:
    payload = _serialize_payload(build_trace_payload())
    resp = await client.post("/traces", json=payload)
    assert resp.status_code == 202
    body = resp.json()
    assert "trace_id" in body
    assert "task_id" in body


async def test_post_trace_missing_name_returns_422(client: AsyncClient) -> None:
    payload = _serialize_payload(build_trace_payload())
    del payload["name"]
    resp = await client.post("/traces", json=payload)
    assert resp.status_code == 422


async def test_post_trace_empty_name_returns_422(client: AsyncClient) -> None:
    payload = _serialize_payload(build_trace_payload(name=""))
    resp = await client.post("/traces", json=payload)
    assert resp.status_code == 422


async def test_post_trace_session_id_exceeds_max_length_returns_422(client: AsyncClient) -> None:
    payload = _serialize_payload(build_trace_payload(session_id="x" * 256))
    resp = await client.post("/traces", json=payload)
    assert resp.status_code == 422


async def test_post_trace_missing_started_at_returns_422(client: AsyncClient) -> None:
    payload = _serialize_payload(build_trace_payload())
    del payload["started_at"]
    resp = await client.post("/traces", json=payload)
    assert resp.status_code == 422


async def test_post_trace_generates_trace_id_if_omitted(client: AsyncClient) -> None:
    payload = _serialize_payload(build_trace_payload())
    del payload["trace_id"]
    resp = await client.post("/traces", json=payload)
    assert resp.status_code == 202
    body = resp.json()
    assert body["trace_id"] is not None


async def test_post_trace_custom_trace_id(client: AsyncClient) -> None:
    custom_id = uuid4()
    payload = _serialize_payload(build_trace_payload(trace_id=custom_id))
    resp = await client.post("/traces", json=payload)
    assert resp.status_code == 202
    assert resp.json()["trace_id"] == str(custom_id)
