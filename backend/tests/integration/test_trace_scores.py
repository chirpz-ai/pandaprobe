"""Integration tests for trace score and metrics endpoints."""

from uuid import uuid4

from httpx import AsyncClient


async def test_list_trace_scores_empty(client: AsyncClient):
    resp = await client.get("/evaluations/trace-scores")
    assert resp.status_code == 200
    data = resp.json()
    assert data["items"] == []
    assert data["total"] == 0


async def test_get_scores_for_trace_empty(client: AsyncClient):
    resp = await client.get(f"/evaluations/trace-scores/{uuid4()}")
    assert resp.status_code == 200
    assert resp.json() == []


async def test_create_trace_score(client: AsyncClient, seed_trace):
    trace = await seed_trace()
    resp = await client.post(
        "/evaluations/trace-scores",
        json={
            "trace_id": str(trace.trace_id),
            "name": "quality",
            "value": "0.9",
            "data_type": "NUMERIC",
            "source": "ANNOTATION",
            "reason": "Looks good",
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["trace_id"] == str(trace.trace_id)
    assert data["name"] == "quality"
    assert data["value"] == "0.9"
    assert data["source"] == "ANNOTATION"
    assert data["status"] == "SUCCESS"
    assert data["reason"] == "Looks good"


async def test_create_trace_score_programmatic(client: AsyncClient, seed_trace):
    trace = await seed_trace()
    resp = await client.post(
        "/evaluations/trace-scores",
        json={
            "trace_id": str(trace.trace_id),
            "name": "thumbs_up",
            "value": "true",
            "data_type": "BOOLEAN",
            "source": "PROGRAMMATIC",
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["data_type"] == "BOOLEAN"
    assert data["source"] == "PROGRAMMATIC"


async def test_patch_trace_score(client: AsyncClient, seed_trace):
    trace = await seed_trace()
    create_resp = await client.post(
        "/evaluations/trace-scores",
        json={
            "trace_id": str(trace.trace_id),
            "name": "quality",
            "value": "0.5",
        },
    )
    score_id = create_resp.json()["id"]

    patch_resp = await client.patch(
        f"/evaluations/trace-scores/{score_id}",
        json={"value": "0.95", "reason": "Revised after review"},
    )
    assert patch_resp.status_code == 200
    data = patch_resp.json()
    assert data["value"] == "0.95"
    assert data["reason"] == "Revised after review"
    assert data["source"] == "ANNOTATION"
    assert data["status"] == "SUCCESS"


async def test_patch_trace_score_not_found(client: AsyncClient):
    resp = await client.patch(
        f"/evaluations/trace-scores/{uuid4()}",
        json={"value": "0.5"},
    )
    assert resp.status_code == 404


async def test_patch_trace_score_rejects_invalid_value(client: AsyncClient, seed_trace):
    """PATCH with value invalid for score's data_type returns 422."""
    trace = await seed_trace()
    create_resp = await client.post(
        "/evaluations/trace-scores",
        json={
            "trace_id": str(trace.trace_id),
            "name": "quality",
            "value": "0.5",
            "data_type": "NUMERIC",
        },
    )
    score_id = create_resp.json()["id"]

    # Invalid: non-numeric for NUMERIC score
    resp = await client.patch(
        f"/evaluations/trace-scores/{score_id}",
        json={"value": "hello"},
    )
    assert resp.status_code == 422

    # Invalid: out of range for NUMERIC score
    resp = await client.patch(
        f"/evaluations/trace-scores/{score_id}",
        json={"value": "1.5"},
    )
    assert resp.status_code == 422

    # Valid update
    resp = await client.patch(
        f"/evaluations/trace-scores/{score_id}",
        json={"value": "0.9"},
    )
    assert resp.status_code == 200
    assert resp.json()["value"] == "0.9"


async def test_delete_trace_score(client: AsyncClient, seed_trace):
    trace = await seed_trace()
    create_resp = await client.post(
        "/evaluations/trace-scores",
        json={
            "trace_id": str(trace.trace_id),
            "name": "to_delete",
            "value": "0.1",
        },
    )
    score_id = create_resp.json()["id"]

    del_resp = await client.delete(f"/evaluations/trace-scores/{score_id}")
    assert del_resp.status_code == 204

    scores_resp = await client.get(f"/evaluations/trace-scores/{trace.trace_id}")
    names = [s["name"] for s in scores_resp.json()]
    assert "to_delete" not in names


async def test_delete_trace_score_not_found(client: AsyncClient):
    resp = await client.delete(f"/evaluations/trace-scores/{uuid4()}")
    assert resp.status_code == 404


async def test_list_metrics(client: AsyncClient):
    resp = await client.get("/evaluations/trace-metrics")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 8
    names = [m["name"] for m in data]
    assert "task_completion" in names
    assert "tool_correctness" in names
    for m in data:
        assert "description" in m
        assert "category" in m
        assert "default_threshold" not in m
        assert "prompt_preview" not in m


async def test_analytics_summary_empty(client: AsyncClient):
    resp = await client.get("/evaluations/analytics/trace-scores/summary")
    assert resp.status_code == 200
    assert resp.json() == []


async def test_analytics_summary_enriched_fields(client: AsyncClient, seed_trace):
    trace = await seed_trace()
    await client.post(
        "/evaluations/trace-scores",
        json={"trace_id": str(trace.trace_id), "name": "quality", "value": "0.8"},
    )
    await client.post(
        "/evaluations/trace-scores",
        json={"trace_id": str(trace.trace_id), "name": "quality", "value": "0.6"},
    )
    resp = await client.get("/evaluations/analytics/trace-scores/summary")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    item = [d for d in data if d["metric_name"] == "quality"][0]
    assert "avg_score" in item
    assert "min_score" in item
    assert "max_score" in item
    assert "median_score" in item
    assert "success_count" in item
    assert "failed_count" in item
    assert "latest_score_at" in item
    assert item["success_count"] == 2
    assert item["min_score"] == 0.6
    assert item["max_score"] == 0.8


async def test_analytics_trend_empty(client: AsyncClient):
    resp = await client.get(
        "/evaluations/analytics/trace-scores/trend",
        params={"metric_name": "task_completion"},
    )
    assert resp.status_code == 200
    assert resp.json() == []


async def test_analytics_distribution_empty(client: AsyncClient):
    resp = await client.get(
        "/evaluations/analytics/trace-scores/distribution",
        params={"metric_name": "task_completion"},
    )
    assert resp.status_code == 200
    assert resp.json() == []


async def test_providers_endpoint(client: AsyncClient):
    resp = await client.get("/evaluations/providers")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
