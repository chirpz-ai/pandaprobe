"""Integration tests for eval run endpoints."""

from uuid import uuid4

from httpx import AsyncClient


async def test_create_eval_run_returns_202(client: AsyncClient, seed_trace):
    await seed_trace()
    resp = await client.post(
        "/evaluations/runs",
        json={
            "metrics": ["task_completion"],
            "filters": {},
        },
    )
    assert resp.status_code == 202
    data = resp.json()
    assert data["status"] == "PENDING"
    assert data["total_traces"] >= 1
    assert data["metric_names"] == ["task_completion"]


async def test_create_eval_run_with_invalid_metric(client: AsyncClient, seed_trace):
    await seed_trace()
    resp = await client.post(
        "/evaluations/runs",
        json={
            "metrics": ["nonexistent_metric"],
            "filters": {},
        },
    )
    assert resp.status_code == 422


async def test_create_eval_run_no_matching_traces(client: AsyncClient):
    resp = await client.post(
        "/evaluations/runs",
        json={
            "metrics": ["task_completion"],
            "filters": {"user_id": "nonexistent-user"},
        },
    )
    assert resp.status_code == 422


async def test_list_eval_runs(client: AsyncClient, seed_trace):
    await seed_trace()
    await client.post(
        "/evaluations/runs",
        json={"metrics": ["task_completion"], "filters": {}},
    )
    resp = await client.get("/evaluations/runs")
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert data["total"] >= 1


async def test_get_eval_run_detail(client: AsyncClient, seed_trace):
    await seed_trace()
    create_resp = await client.post(
        "/evaluations/runs",
        json={"metrics": ["task_completion"], "filters": {}},
    )
    run_id = create_resp.json()["id"]
    resp = await client.get(f"/evaluations/runs/{run_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == run_id


async def test_get_eval_run_not_found(client: AsyncClient):
    resp = await client.get(f"/evaluations/runs/{uuid4()}")
    assert resp.status_code == 404
