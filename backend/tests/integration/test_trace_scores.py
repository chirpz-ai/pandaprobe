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


async def test_list_metrics(client: AsyncClient):
    resp = await client.get("/evaluations/metrics")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 6
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
