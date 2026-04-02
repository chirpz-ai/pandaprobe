"""Integration tests for session eval run and session score endpoints."""

from datetime import datetime, timezone
from uuid import uuid4

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.db.models import EvalRunModel, SessionScoreModel
from app.registry.constants import EvaluationStatus, ScoreDataType, ScoreSource, ScoreStatus


# ---------------------------------------------------------------------------
# Session eval run creation
# ---------------------------------------------------------------------------


async def test_create_session_eval_run_returns_202(client: AsyncClient, seed_trace):
    await seed_trace(session_id="sess-1")
    resp = await client.post(
        "/evaluations/session-runs",
        json={
            "metrics": ["agent_reliability"],
            "filters": {},
        },
    )
    assert resp.status_code == 202
    data = resp.json()
    assert data["status"] == "PENDING"
    assert data["target_type"] == "SESSION"
    assert data["total_targets"] >= 1
    assert data["metric_names"] == ["agent_reliability"]


async def test_create_session_eval_run_invalid_metric(client: AsyncClient, seed_trace):
    await seed_trace(session_id="sess-1")
    resp = await client.post(
        "/evaluations/session-runs",
        json={
            "metrics": ["nonexistent_session_metric"],
            "filters": {},
        },
    )
    assert resp.status_code == 422


async def test_create_session_eval_run_no_sessions(client: AsyncClient):
    resp = await client.post(
        "/evaluations/session-runs",
        json={
            "metrics": ["agent_reliability"],
            "filters": {"user_id": "no-such-user"},
        },
    )
    assert resp.status_code == 422


async def test_create_batch_session_eval_run(client: AsyncClient, seed_trace):
    await seed_trace(session_id="sess-batch-1")
    resp = await client.post(
        "/evaluations/session-runs/batch",
        json={
            "session_ids": ["sess-batch-1"],
            "metrics": ["agent_reliability", "agent_consistency"],
        },
    )
    assert resp.status_code == 202
    data = resp.json()
    assert data["status"] == "PENDING"
    assert data["target_type"] == "SESSION"
    assert set(data["metric_names"]) == {"agent_reliability", "agent_consistency"}


async def test_create_batch_session_eval_run_empty_ids(client: AsyncClient):
    resp = await client.post(
        "/evaluations/session-runs/batch",
        json={
            "session_ids": [],
            "metrics": ["agent_reliability"],
        },
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Session eval run list / detail / delete
# ---------------------------------------------------------------------------


async def test_list_session_eval_runs(client: AsyncClient, seed_trace):
    await seed_trace(session_id="sess-list")
    await client.post(
        "/evaluations/session-runs",
        json={"metrics": ["agent_reliability"], "filters": {}},
    )
    resp = await client.get("/evaluations/session-runs")
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert data["total"] >= 1
    assert all(item["target_type"] == "SESSION" for item in data["items"])


async def test_get_session_eval_run_detail(client: AsyncClient, seed_trace):
    await seed_trace(session_id="sess-detail")
    create_resp = await client.post(
        "/evaluations/session-runs",
        json={"metrics": ["agent_reliability"], "filters": {}},
    )
    run_id = create_resp.json()["id"]
    resp = await client.get(f"/evaluations/session-runs/{run_id}")
    assert resp.status_code == 200
    assert resp.json()["id"] == run_id


async def test_get_session_eval_run_not_found(client: AsyncClient):
    resp = await client.get(f"/evaluations/session-runs/{uuid4()}")
    assert resp.status_code == 404


async def test_delete_session_eval_run(client: AsyncClient, seed_trace):
    await seed_trace(session_id="sess-del")
    create_resp = await client.post(
        "/evaluations/session-runs",
        json={"metrics": ["agent_reliability"], "filters": {}},
    )
    run_id = create_resp.json()["id"]
    resp = await client.delete(f"/evaluations/session-runs/{run_id}")
    assert resp.status_code == 204
    get_resp = await client.get(f"/evaluations/session-runs/{run_id}")
    assert get_resp.status_code == 404


async def test_delete_session_eval_run_not_found(client: AsyncClient):
    resp = await client.delete(f"/evaluations/session-runs/{uuid4()}")
    assert resp.status_code == 404


async def test_get_session_run_scores_empty(client: AsyncClient, seed_trace):
    await seed_trace(session_id="sess-scores")
    create_resp = await client.post(
        "/evaluations/session-runs",
        json={"metrics": ["agent_reliability"], "filters": {}},
    )
    run_id = create_resp.json()["id"]
    resp = await client.get(f"/evaluations/session-runs/{run_id}/scores")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


# ---------------------------------------------------------------------------
# Session eval run retry
# ---------------------------------------------------------------------------


async def test_retry_session_run_no_failures_returns_422(client: AsyncClient, seed_trace, db_session: AsyncSession):
    trace = await seed_trace(session_id="sess-retry")
    now = datetime.now(timezone.utc)
    run_id = uuid4()
    project_id = trace.project_id

    db_session.add(
        EvalRunModel(
            id=run_id,
            project_id=project_id,
            name="completed-session-run",
            target_type="SESSION",
            metric_names=["agent_reliability"],
            filters={},
            sampling_rate=1.0,
            status=EvaluationStatus.COMPLETED,
            total_targets=1,
            evaluated_count=1,
            created_at=now,
        )
    )
    db_session.add(
        SessionScoreModel(
            id=uuid4(),
            session_id="sess-retry",
            project_id=project_id,
            name="agent_reliability",
            data_type=ScoreDataType.NUMERIC,
            value="0.85",
            source=ScoreSource.AUTOMATED,
            status=ScoreStatus.SUCCESS,
            eval_run_id=run_id,
            created_at=now,
        )
    )
    await db_session.commit()

    resp = await client.post(f"/evaluations/session-runs/{run_id}/retry")
    assert resp.status_code == 422


async def test_retry_session_run_with_failures_returns_202(client: AsyncClient, seed_trace, db_session: AsyncSession):
    trace = await seed_trace(session_id="sess-retry-fail")
    now = datetime.now(timezone.utc)
    run_id = uuid4()
    project_id = trace.project_id

    db_session.add(
        EvalRunModel(
            id=run_id,
            project_id=project_id,
            name="failed-session-run",
            target_type="SESSION",
            metric_names=["agent_reliability"],
            filters={},
            sampling_rate=1.0,
            status=EvaluationStatus.COMPLETED,
            total_targets=1,
            evaluated_count=1,
            failed_count=1,
            created_at=now,
        )
    )
    db_session.add(
        SessionScoreModel(
            id=uuid4(),
            session_id="sess-retry-fail",
            project_id=project_id,
            name="agent_reliability",
            data_type=ScoreDataType.NUMERIC,
            value=None,
            source=ScoreSource.AUTOMATED,
            status=ScoreStatus.FAILED,
            eval_run_id=run_id,
            reason="LLM call failed",
            created_at=now,
        )
    )
    await db_session.commit()

    resp = await client.post(f"/evaluations/session-runs/{run_id}/retry")
    assert resp.status_code == 202
    data = resp.json()
    assert data["status"] == "PENDING"
    assert data["target_type"] == "SESSION"
    assert "Retry" in data["name"]


# ---------------------------------------------------------------------------
# Session scores
# ---------------------------------------------------------------------------


async def test_list_session_scores_empty(client: AsyncClient):
    resp = await client.get("/evaluations/session-scores")
    assert resp.status_code == 200
    data = resp.json()
    assert data["items"] == []
    assert data["total"] == 0


async def test_get_scores_for_session_empty(client: AsyncClient):
    resp = await client.get("/evaluations/session-scores/nonexistent-session")
    assert resp.status_code == 200
    assert resp.json() == []


async def test_delete_session_score(client: AsyncClient, seed_trace, db_session: AsyncSession):
    trace = await seed_trace(session_id="sess-del-score")
    now = datetime.now(timezone.utc)
    score_id = uuid4()

    db_session.add(
        SessionScoreModel(
            id=score_id,
            session_id="sess-del-score",
            project_id=trace.project_id,
            name="agent_reliability",
            data_type=ScoreDataType.NUMERIC,
            value="0.7",
            source=ScoreSource.AUTOMATED,
            status=ScoreStatus.SUCCESS,
            created_at=now,
        )
    )
    await db_session.commit()

    resp = await client.delete(f"/evaluations/session-scores/{score_id}")
    assert resp.status_code == 204


# ---------------------------------------------------------------------------
# Session metric discovery
# ---------------------------------------------------------------------------


async def test_list_session_metrics_endpoint(client: AsyncClient):
    resp = await client.get("/evaluations/session-metrics")
    assert resp.status_code == 200
    data = resp.json()
    names = [m["name"] for m in data]
    assert "agent_reliability" in names
    assert "agent_consistency" in names
    for m in data:
        assert "description" in m
        assert "category" in m


# ---------------------------------------------------------------------------
# Session score analytics
# ---------------------------------------------------------------------------


async def test_session_analytics_summary_empty(client: AsyncClient):
    resp = await client.get("/evaluations/analytics/session-scores/summary")
    assert resp.status_code == 200
    assert resp.json() == []


async def test_session_analytics_trend_empty(client: AsyncClient):
    resp = await client.get(
        "/evaluations/analytics/session-scores/trend",
        params={"metric_name": "agent_reliability"},
    )
    assert resp.status_code == 200
    assert resp.json() == []
