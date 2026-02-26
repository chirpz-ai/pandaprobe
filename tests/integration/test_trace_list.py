"""Integration tests for trace listing, filtering, sorting, and pagination."""

from datetime import datetime, timedelta, timezone

from httpx import AsyncClient

from .factories import build_span_payload


async def _seed_varied_traces(seed_trace, count: int = 15):
    """Insert traces with diverse attributes for filter/sort/page tests."""
    now = datetime.now(timezone.utc)
    traces = []
    for i in range(count):
        started = now - timedelta(hours=count - i)
        ended = started + timedelta(seconds=1 + i)
        status = "ERROR" if i % 5 == 0 else "COMPLETED"
        span = build_span_payload(
            name=f"span-{i}",
            started_at=started,
            ended_at=started + timedelta(milliseconds=800),
            model="gpt-4o" if i % 3 == 0 else None,
            token_usage={"prompt_tokens": 10 * (i + 1), "completion_tokens": 5 * (i + 1)} if i % 3 == 0 else None,
            cost={"total": 0.01 * (i + 1)} if i % 3 == 0 else None,
        )
        t = await seed_trace(
            name=f"trace-{i:02d}",
            status=status,
            user_id=f"user-{i % 3}",
            session_id=f"sess-{i % 4}",
            tags=[f"tag-{i % 2}"],
            started_at=started,
            ended_at=ended,
            spans=[span],
        )
        traces.append(t)
    return traces


async def test_list_traces_default(client: AsyncClient, seed_trace) -> None:
    await _seed_varied_traces(seed_trace, count=5)
    resp = await client.get("/traces")
    assert resp.status_code == 200
    body = resp.json()
    assert "items" in body
    assert "total" in body
    assert body["total"] == 5
    assert len(body["items"]) == 5


async def test_list_traces_pagination(client: AsyncClient, seed_trace) -> None:
    await _seed_varied_traces(seed_trace, count=12)
    page1 = await client.get("/traces", params={"limit": 5, "offset": 0})
    page2 = await client.get("/traces", params={"limit": 5, "offset": 5})
    page3 = await client.get("/traces", params={"limit": 5, "offset": 10})

    assert page1.status_code == 200
    assert page2.status_code == 200
    assert page3.status_code == 200

    ids1 = {item["trace_id"] for item in page1.json()["items"]}
    ids2 = {item["trace_id"] for item in page2.json()["items"]}
    assert len(ids1) == 5
    assert len(ids2) == 5
    assert ids1.isdisjoint(ids2)

    assert page1.json()["total"] == 12


async def test_list_traces_filter_by_name(client: AsyncClient, seed_trace) -> None:
    await seed_trace(name="alpha-run")
    await seed_trace(name="beta-run")
    resp = await client.get("/traces", params={"name": "alpha"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] >= 1
    assert all("alpha" in item["name"] for item in body["items"])


async def test_list_traces_filter_by_status(client: AsyncClient, seed_trace) -> None:
    await seed_trace(status="ERROR")
    await seed_trace(status="COMPLETED")
    await seed_trace(status="COMPLETED")
    resp = await client.get("/traces", params={"status": "ERROR"})
    assert resp.status_code == 200
    assert all(item["status"] == "ERROR" for item in resp.json()["items"])


async def test_list_traces_filter_by_user_id(client: AsyncClient, seed_trace) -> None:
    await seed_trace(user_id="alice")
    await seed_trace(user_id="bob")
    resp = await client.get("/traces", params={"user_id": "alice"})
    assert resp.status_code == 200
    assert all(item["user_id"] == "alice" for item in resp.json()["items"])


async def test_list_traces_filter_by_session_id(client: AsyncClient, seed_trace) -> None:
    await seed_trace(session_id="sess-x")
    await seed_trace(session_id="sess-y")
    resp = await client.get("/traces", params={"session_id": "sess-x"})
    assert resp.status_code == 200
    assert all(item["session_id"] == "sess-x" for item in resp.json()["items"])


async def test_list_traces_filter_by_tags(client: AsyncClient, seed_trace) -> None:
    await seed_trace(tags=["production", "gpt"])
    await seed_trace(tags=["staging"])
    resp = await client.get("/traces", params={"tags": "production"})
    assert resp.status_code == 200
    assert all("production" in item["tags"] for item in resp.json()["items"])


async def test_list_traces_filter_by_date_range(client: AsyncClient, seed_trace) -> None:
    now = datetime.now(timezone.utc)
    old = now - timedelta(days=10)
    recent = now - timedelta(hours=1)
    await seed_trace(name="old", started_at=old, ended_at=old + timedelta(seconds=1))
    await seed_trace(name="recent", started_at=recent, ended_at=recent + timedelta(seconds=1))
    resp = await client.get(
        "/traces",
        params={
            "started_after": (now - timedelta(days=1)).isoformat(),
            "started_before": now.isoformat(),
        },
    )
    assert resp.status_code == 200
    names = [item["name"] for item in resp.json()["items"]]
    assert "recent" in names
    assert "old" not in names


async def test_list_traces_sort_asc(client: AsyncClient, seed_trace) -> None:
    now = datetime.now(timezone.utc)
    await seed_trace(name="early", started_at=now - timedelta(hours=2), ended_at=now - timedelta(hours=1))
    await seed_trace(name="late", started_at=now - timedelta(minutes=10), ended_at=now)
    resp = await client.get("/traces", params={"sort_by": "started_at", "sort_order": "asc"})
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) >= 2
    assert items[0]["started_at"] <= items[-1]["started_at"]


async def test_list_traces_sort_desc(client: AsyncClient, seed_trace) -> None:
    now = datetime.now(timezone.utc)
    await seed_trace(name="early", started_at=now - timedelta(hours=2), ended_at=now - timedelta(hours=1))
    await seed_trace(name="late", started_at=now - timedelta(minutes=10), ended_at=now)
    resp = await client.get("/traces", params={"sort_by": "started_at", "sort_order": "desc"})
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert items[0]["started_at"] >= items[-1]["started_at"]


async def test_list_traces_computed_fields(client: AsyncClient, seed_trace) -> None:
    now = datetime.now(timezone.utc)
    span = build_span_payload(
        started_at=now - timedelta(seconds=1),
        ended_at=now,
        model="gpt-4o",
        token_usage={"prompt_tokens": 10, "completion_tokens": 5},
        cost={"total": 0.005},
    )
    await seed_trace(
        name="with-stats",
        started_at=now - timedelta(seconds=2),
        ended_at=now,
        spans=[span],
    )
    resp = await client.get("/traces", params={"name": "with-stats"})
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) >= 1
    item = items[0]
    assert item["span_count"] >= 1
    assert item["latency_ms"] is not None
    assert item["latency_ms"] > 0
    assert item["total_tokens"] >= 15
    assert item["total_cost"] > 0
