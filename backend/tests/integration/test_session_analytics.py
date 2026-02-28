"""Integration tests for session time-series analytics."""

from datetime import datetime, timedelta, timezone

from httpx import AsyncClient


async def test_session_analytics_by_day(client: AsyncClient, seed_trace) -> None:
    now = datetime.now(timezone.utc)
    day1 = now - timedelta(days=2)
    day2 = now - timedelta(days=1)

    for i in range(3):
        started = day1 + timedelta(hours=i)
        await seed_trace(
            session_id=f"day1-sess-{i}",
            started_at=started,
            ended_at=started + timedelta(seconds=2),
        )
    for i in range(2):
        started = day2 + timedelta(hours=i)
        await seed_trace(
            session_id=f"day2-sess-{i}",
            started_at=started,
            ended_at=started + timedelta(seconds=3),
        )

    resp = await client.get(
        "/sessions/analytics",
        params={
            "granularity": "day",
            "started_after": (now - timedelta(days=3)).isoformat(),
            "started_before": now.isoformat(),
        },
    )
    assert resp.status_code == 200
    buckets = resp.json()
    assert isinstance(buckets, list)
    total_sessions = sum(b["session_count"] for b in buckets)
    assert total_sessions == 5


async def test_session_analytics_empty_range(client: AsyncClient) -> None:
    far_future = datetime.now(timezone.utc) + timedelta(days=365)
    resp = await client.get(
        "/sessions/analytics",
        params={
            "granularity": "day",
            "started_after": far_future.isoformat(),
            "started_before": (far_future + timedelta(days=1)).isoformat(),
        },
    )
    assert resp.status_code == 200
    assert resp.json() == []


async def test_session_analytics_avg_fields(client: AsyncClient, seed_trace) -> None:
    now = datetime.now(timezone.utc)
    session_id = "multi-trace-sess"
    for i in range(3):
        started = now - timedelta(hours=1, minutes=i * 10)
        await seed_trace(
            session_id=session_id,
            started_at=started,
            ended_at=started + timedelta(seconds=2),
        )

    resp = await client.get(
        "/sessions/analytics",
        params={
            "granularity": "day",
            "started_after": (now - timedelta(days=1)).isoformat(),
            "started_before": now.isoformat(),
        },
    )
    assert resp.status_code == 200
    buckets = resp.json()
    assert len(buckets) >= 1
    bucket = buckets[0]
    assert "session_count" in bucket
    assert "avg_traces_per_session" in bucket
    assert "avg_session_duration_ms" in bucket
