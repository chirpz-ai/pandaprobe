"""Integration tests for batch trace operations (delete, tag updates)."""

from uuid import uuid4

from httpx import AsyncClient


async def test_batch_delete_removes_selected_traces(client: AsyncClient, seed_trace) -> None:
    traces = [await seed_trace(name=f"batch-{i}") for i in range(5)]
    to_delete = [str(traces[0].trace_id), str(traces[1].trace_id), str(traces[2].trace_id)]

    resp = await client.post("/traces/batch/delete", json={"trace_ids": to_delete})
    assert resp.status_code == 200
    assert resp.json()["deleted"] == 3

    listing = await client.get("/traces")
    remaining_ids = {item["trace_id"] for item in listing.json()["items"]}
    for tid in to_delete:
        assert tid not in remaining_ids
    assert str(traces[3].trace_id) in remaining_ids
    assert str(traces[4].trace_id) in remaining_ids


async def test_batch_delete_nonexistent_ids_returns_zero(client: AsyncClient) -> None:
    resp = await client.post(
        "/traces/batch/delete",
        json={"trace_ids": [str(uuid4()), str(uuid4())]},
    )
    assert resp.status_code == 200
    assert resp.json()["deleted"] == 0


async def test_batch_add_tags(client: AsyncClient, seed_trace) -> None:
    t1 = await seed_trace(tags=["existing"])
    t2 = await seed_trace(tags=["existing"])
    resp = await client.post(
        "/traces/batch/tags",
        json={
            "trace_ids": [str(t1.trace_id), str(t2.trace_id)],
            "add_tags": ["new-tag", "existing"],
        },
    )
    assert resp.status_code == 200
    assert resp.json()["updated"] == 2

    for tid in [t1.trace_id, t2.trace_id]:
        detail = await client.get(f"/traces/{tid}")
        tags = detail.json()["tags"]
        assert "new-tag" in tags
        assert "existing" in tags


async def test_batch_remove_tags(client: AsyncClient, seed_trace) -> None:
    t1 = await seed_trace(tags=["keep", "remove-me"])
    resp = await client.post(
        "/traces/batch/tags",
        json={
            "trace_ids": [str(t1.trace_id)],
            "remove_tags": ["remove-me"],
        },
    )
    assert resp.status_code == 200
    detail = await client.get(f"/traces/{t1.trace_id}")
    tags = detail.json()["tags"]
    assert "keep" in tags
    assert "remove-me" not in tags


async def test_batch_add_and_remove_tags(client: AsyncClient, seed_trace) -> None:
    t1 = await seed_trace(tags=["a", "b"])
    resp = await client.post(
        "/traces/batch/tags",
        json={
            "trace_ids": [str(t1.trace_id)],
            "add_tags": ["c"],
            "remove_tags": ["b"],
        },
    )
    assert resp.status_code == 200
    detail = await client.get(f"/traces/{t1.trace_id}")
    tags = detail.json()["tags"]
    assert "a" in tags
    assert "c" in tags
    assert "b" not in tags


async def test_batch_tags_empty_lists_returns_zero(client: AsyncClient, seed_trace) -> None:
    t1 = await seed_trace(tags=["x"])
    resp = await client.post(
        "/traces/batch/tags",
        json={
            "trace_ids": [str(t1.trace_id)],
            "add_tags": [],
            "remove_tags": [],
        },
    )
    assert resp.status_code == 200
    assert resp.json()["updated"] == 0
