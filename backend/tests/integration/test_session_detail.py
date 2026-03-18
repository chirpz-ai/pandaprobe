"""Integration tests for single-session detail and deletion."""

from datetime import datetime, timedelta, timezone

from httpx import AsyncClient

from .factories import build_span_payload


async def test_get_session_detail(client: AsyncClient, seed_trace) -> None:
    now = datetime.now(timezone.utc)
    session_id = "detail-sess"
    for i in range(5):
        started = now - timedelta(hours=5 - i)
        ended = started + timedelta(seconds=2)
        span = build_span_payload(
            started_at=started,
            ended_at=started + timedelta(milliseconds=800),
            model="gpt-4o",
            token_usage={"prompt_tokens": 10, "completion_tokens": 5},
            cost={"total": 0.003},
        )
        await seed_trace(
            session_id=session_id,
            name=f"detail-trace-{i}",
            started_at=started,
            ended_at=ended,
            input={"prompt": f"hello-{i}"},
            output={"response": f"bye-{i}"},
            spans=[span],
        )

    resp = await client.get(f"/sessions/{session_id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["session_id"] == session_id
    assert body["trace_count"] == 5
    assert body["total_span_count"] >= 5
    assert body["total_tokens"] >= 75
    assert body["total_cost"] > 0
    assert "first_trace_at" in body
    assert "last_trace_at" in body
    assert "input" not in body
    assert "output" not in body

    traces = body["traces"]
    assert len(traces) == 5
    for t in traces:
        assert "input" in t
        assert "output" in t
        assert "spans" in t
        assert "project_id" in t


async def test_get_session_detail_full_traces(client: AsyncClient, seed_trace) -> None:
    """Each trace in the response includes input, output, and spans."""
    now = datetime.now(timezone.utc)
    session_id = "full-trace-sess"
    await seed_trace(
        session_id=session_id,
        name="first",
        started_at=now - timedelta(hours=2),
        ended_at=now - timedelta(hours=1),
        input={"prompt": "first-input"},
        output={"response": "first-output"},
        spans=[
            build_span_payload(
                started_at=now - timedelta(hours=2),
                ended_at=now - timedelta(hours=1),
            )
        ],
    )
    await seed_trace(
        session_id=session_id,
        name="last",
        started_at=now - timedelta(minutes=10),
        ended_at=now,
        input={"prompt": "last-input"},
        output={"response": "last-output"},
        spans=[
            build_span_payload(
                started_at=now - timedelta(minutes=10),
                ended_at=now,
            )
        ],
    )

    resp = await client.get(f"/sessions/{session_id}")
    assert resp.status_code == 200
    body = resp.json()
    traces = body["traces"]
    assert len(traces) == 2
    assert traces[0]["name"] == "first"
    assert traces[0]["input"] == {"prompt": "first-input"}
    assert traces[0]["output"] == {"response": "first-output"}
    assert len(traces[0]["spans"]) >= 1
    assert traces[1]["name"] == "last"
    assert traces[1]["input"] == {"prompt": "last-input"}
    assert traces[1]["output"] == {"response": "last-output"}


async def test_get_session_detail_pagination(client: AsyncClient, seed_trace) -> None:
    now = datetime.now(timezone.utc)
    session_id = "paged-sess"
    for i in range(5):
        started = now - timedelta(hours=5 - i)
        await seed_trace(
            session_id=session_id,
            name=f"paged-{i}",
            started_at=started,
            ended_at=started + timedelta(seconds=1),
        )

    page1 = await client.get(f"/sessions/{session_id}", params={"limit": 2, "offset": 0})
    page2 = await client.get(f"/sessions/{session_id}", params={"limit": 2, "offset": 2})
    assert page1.status_code == 200
    assert page2.status_code == 200
    assert page1.json()["trace_count"] == 5
    ids1 = {t["trace_id"] for t in page1.json()["traces"]}
    ids2 = {t["trace_id"] for t in page2.json()["traces"]}
    assert ids1.isdisjoint(ids2)


async def test_get_nonexistent_session_returns_404(client: AsyncClient) -> None:
    resp = await client.get("/sessions/does-not-exist")
    assert resp.status_code == 404


async def test_delete_session_removes_all_traces(client: AsyncClient, seed_trace) -> None:
    now = datetime.now(timezone.utc)
    session_id = "delete-me"
    for i in range(3):
        started = now - timedelta(hours=3 - i)
        await seed_trace(
            session_id=session_id,
            started_at=started,
            ended_at=started + timedelta(seconds=1),
        )

    resp = await client.delete(f"/sessions/{session_id}")
    assert resp.status_code == 200
    assert resp.json()["deleted"] == 3

    detail = await client.get(f"/sessions/{session_id}")
    assert detail.status_code == 404
