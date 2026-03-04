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
    assert "project_id" in data
    assert "filters" in data
    assert "sampling_rate" in data


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


async def test_create_batch_eval_run(client: AsyncClient, seed_trace):
    trace = await seed_trace()
    resp = await client.post(
        "/evaluations/runs/batch",
        json={
            "trace_ids": [str(trace.trace_id)],
            "metrics": ["task_completion", "step_efficiency"],
        },
    )
    assert resp.status_code == 202
    data = resp.json()
    assert data["status"] == "PENDING"
    assert data["total_traces"] == 1
    assert set(data["metric_names"]) == {"task_completion", "step_efficiency"}


async def test_create_batch_eval_run_empty_traces(client: AsyncClient):
    resp = await client.post(
        "/evaluations/runs/batch",
        json={
            "trace_ids": [],
            "metrics": ["task_completion"],
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
    item = data["items"][0]
    assert "id" in item
    assert "status" in item
    assert "metric_names" in item
    assert "project_id" in item
    assert "filters" in item
    assert "sampling_rate" in item


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
    assert "project_id" in data
    assert "filters" in data
    assert "sampling_rate" in data
    assert "error_message" in data


async def test_get_eval_run_not_found(client: AsyncClient):
    resp = await client.get(f"/evaluations/runs/{uuid4()}")
    assert resp.status_code == 404


async def test_get_run_template(client: AsyncClient):
    resp = await client.get("/evaluations/runs/template", params={"metric": "task_completion"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["metric"]["name"] == "task_completion"
    assert len(data["metric"]["prompt_preview"]) > 0
    assert data["sampling_rate"] == 1.0
    assert "filters" in data
    assert data["model"] is not None
