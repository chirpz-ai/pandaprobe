"""Integration tests for single-trace CRUD operations.

Data is seeded directly via ``seed_trace`` (repository insert within the
test transaction).  GET, PATCH, and DELETE are exercised through the API.
"""

from uuid import uuid4

from httpx import AsyncClient

from .factories import build_span_payload


async def test_get_trace_returns_seeded_data(client: AsyncClient, seed_trace) -> None:
    trace = await seed_trace(name="crud-get", tags=["a", "b"])
    resp = await client.get(f"/traces/{trace.trace_id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "crud-get"
    assert set(body["tags"]) == {"a", "b"}
    assert body["trace_id"] == str(trace.trace_id)


async def test_get_nonexistent_trace_returns_404(client: AsyncClient) -> None:
    resp = await client.get(f"/traces/{uuid4()}")
    assert resp.status_code == 404


async def test_patch_trace_updates_fields(client: AsyncClient, seed_trace) -> None:
    trace = await seed_trace(name="original")
    resp = await client.patch(
        f"/traces/{trace.trace_id}",
        json={"name": "updated", "tags": ["new-tag"], "session_id": "sess-99"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "updated"
    assert "new-tag" in body["tags"]
    assert body["session_id"] == "sess-99"


async def test_patch_clears_nullable_field(client: AsyncClient, seed_trace) -> None:
    trace = await seed_trace(session_id="to-clear")
    resp = await client.patch(
        f"/traces/{trace.trace_id}",
        json={"session_id": None},
    )
    assert resp.status_code == 200
    assert resp.json()["session_id"] is None


async def test_patch_ignores_null_for_non_nullable_field(client: AsyncClient, seed_trace) -> None:
    trace = await seed_trace(name="keep-status", status="COMPLETED")

    resp = await client.patch(
        f"/traces/{trace.trace_id}",
        json={"status": None},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "COMPLETED"


async def test_patch_nonexistent_trace_returns_404(client: AsyncClient) -> None:
    resp = await client.patch(f"/traces/{uuid4()}", json={"name": "nope"})
    assert resp.status_code == 404


async def test_delete_trace_returns_204(client: AsyncClient, seed_trace) -> None:
    trace = await seed_trace(name="to-delete")
    resp = await client.delete(f"/traces/{trace.trace_id}")
    assert resp.status_code == 204

    resp = await client.get(f"/traces/{trace.trace_id}")
    assert resp.status_code == 404


async def test_delete_nonexistent_trace_returns_404(client: AsyncClient) -> None:
    resp = await client.delete(f"/traces/{uuid4()}")
    assert resp.status_code == 404


async def test_get_trace_includes_spans(client: AsyncClient, seed_trace) -> None:
    span = build_span_payload(name="my-span", kind="LLM", model="gpt-4o")
    trace = await seed_trace(name="with-spans", spans=[span])

    resp = await client.get(f"/traces/{trace.trace_id}")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["spans"]) == 1
    assert body["spans"][0]["name"] == "my-span"
    assert body["spans"][0]["model"] == "gpt-4o"


async def test_patch_response_omits_spans(client: AsyncClient, seed_trace) -> None:
    """A trace update must not echo the trace's spans back.

    Spans accumulate without a ceiling across repeated appends, so returning them
    grew the response unboundedly: one production trace reached ~29 MB of span
    payloads and the reply exceeded Cloud Run's response limit. The write had
    already committed, so every SDK retry of an applied update failed again.
    """
    spans = [build_span_payload() for _ in range(3)]
    trace = await seed_trace(name="patch-no-spans", spans=spans)

    resp = await client.patch(f"/traces/{trace.trace_id}", json={"name": "renamed"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "renamed"
    assert "spans" not in body, "PATCH must not serialise spans"
    # The summary fields callers rely on are still present.
    assert body["trace_id"] == str(trace.trace_id)
    assert "total_tokens" in body
