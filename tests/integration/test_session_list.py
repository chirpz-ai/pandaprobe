"""Integration tests for session listing and filtering."""

from datetime import datetime, timedelta, timezone

from httpx import AsyncClient

from .factories import build_span_payload


async def _seed_sessions(seed_trace, session_count: int = 3, traces_per_session: int = 2):
    """Create multiple sessions, each with several traces."""
    now = datetime.now(timezone.utc)
    for s in range(session_count):
        session_id = f"session-{s}"
        for t in range(traces_per_session):
            started = now - timedelta(hours=session_count - s, minutes=t * 10)
            ended = started + timedelta(seconds=2)
            status = "ERROR" if s == 0 and t == 0 else "COMPLETED"
            span = build_span_payload(
                started_at=started,
                ended_at=started + timedelta(milliseconds=800),
                model="gpt-4o",
                token_usage={"prompt_tokens": 10, "completion_tokens": 5},
                cost={"total": 0.003},
            )
            await seed_trace(
                session_id=session_id,
                name=f"trace-s{s}-t{t}",
                user_id=f"user-{s % 2}",
                status=status,
                started_at=started,
                ended_at=ended,
                tags=[f"env-{s}"],
                spans=[span],
            )


async def test_list_sessions_returns_summaries(client: AsyncClient, seed_trace) -> None:
    await _seed_sessions(seed_trace)
    resp = await client.get("/sessions")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 3
    for item in body["items"]:
        assert "session_id" in item
        assert "trace_count" in item
        assert item["trace_count"] >= 1
        assert "first_trace_at" in item
        assert "has_error" in item


async def test_list_sessions_aggregated_fields(client: AsyncClient, seed_trace) -> None:
    await _seed_sessions(seed_trace)
    resp = await client.get("/sessions")
    body = resp.json()
    for item in body["items"]:
        assert "total_span_count" in item
        assert "total_tokens" in item
        assert "total_cost" in item
        assert item["total_span_count"] >= 0
        assert item["total_tokens"] >= 0


async def test_list_sessions_filter_by_user_id(client: AsyncClient, seed_trace) -> None:
    await _seed_sessions(seed_trace)
    resp = await client.get("/sessions", params={"user_id": "user-0"})
    assert resp.status_code == 200
    for item in resp.json()["items"]:
        assert item["user_id"] == "user-0"


async def test_list_sessions_filter_by_has_error(client: AsyncClient, seed_trace) -> None:
    await _seed_sessions(seed_trace)
    resp = await client.get("/sessions", params={"has_error": "true"})
    assert resp.status_code == 200
    for item in resp.json()["items"]:
        assert item["has_error"] is True


async def test_list_sessions_filter_by_date_range(client: AsyncClient, seed_trace) -> None:
    now = datetime.now(timezone.utc)
    old = now - timedelta(days=10)
    recent = now - timedelta(hours=1)
    await seed_trace(session_id="old-sess", started_at=old, ended_at=old + timedelta(seconds=1))
    await seed_trace(session_id="new-sess", started_at=recent, ended_at=recent + timedelta(seconds=1))

    resp = await client.get(
        "/sessions",
        params={
            "started_after": (now - timedelta(days=1)).isoformat(),
            "started_before": now.isoformat(),
        },
    )
    assert resp.status_code == 200
    session_ids = [item["session_id"] for item in resp.json()["items"]]
    assert "new-sess" in session_ids
    assert "old-sess" not in session_ids


async def test_list_sessions_filter_by_query(client: AsyncClient, seed_trace) -> None:
    await seed_trace(session_id="chat-abc-123")
    await seed_trace(session_id="workflow-xyz")

    resp = await client.get("/sessions", params={"query": "chat"})
    assert resp.status_code == 200
    session_ids = [item["session_id"] for item in resp.json()["items"]]
    assert "chat-abc-123" in session_ids
    assert "workflow-xyz" not in session_ids


async def test_list_sessions_pagination(client: AsyncClient, seed_trace) -> None:
    for i in range(6):
        await seed_trace(session_id=f"page-sess-{i}")

    page1 = await client.get("/sessions", params={"limit": 3, "offset": 0})
    page2 = await client.get("/sessions", params={"limit": 3, "offset": 3})
    assert page1.status_code == 200
    assert page2.status_code == 200

    ids1 = {item["session_id"] for item in page1.json()["items"]}
    ids2 = {item["session_id"] for item in page2.json()["items"]}
    assert len(ids1) == 3
    assert len(ids2) == 3
    assert ids1.isdisjoint(ids2)
