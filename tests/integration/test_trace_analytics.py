"""Integration tests for trace time-series analytics."""

from datetime import datetime, timedelta, timezone

from httpx import AsyncClient

from .factories import build_span_payload


async def test_analytics_volume_by_day(client: AsyncClient, seed_trace) -> None:
    now = datetime.now(timezone.utc)
    day1 = now - timedelta(days=2)
    day2 = now - timedelta(days=1)

    for i in range(3):
        started = day1 + timedelta(hours=i)
        await seed_trace(started_at=started, ended_at=started + timedelta(seconds=1))
    for i in range(2):
        started = day2 + timedelta(hours=i)
        await seed_trace(started_at=started, ended_at=started + timedelta(seconds=1))

    resp = await client.get(
        "/traces/analytics",
        params={
            "metric": "volume",
            "granularity": "day",
            "started_after": (now - timedelta(days=3)).isoformat(),
            "started_before": now.isoformat(),
        },
    )
    assert resp.status_code == 200
    buckets = resp.json()
    assert isinstance(buckets, list)
    total = sum(b["trace_count"] for b in buckets)
    assert total == 5


async def test_analytics_latency_by_day(client: AsyncClient, seed_trace) -> None:
    now = datetime.now(timezone.utc)
    started = now - timedelta(hours=2)
    await seed_trace(started_at=started, ended_at=started + timedelta(seconds=2))

    resp = await client.get(
        "/traces/analytics",
        params={
            "metric": "latency",
            "granularity": "day",
            "started_after": (now - timedelta(days=1)).isoformat(),
            "started_before": now.isoformat(),
        },
    )
    assert resp.status_code == 200
    buckets = resp.json()
    assert len(buckets) >= 1
    assert buckets[0]["avg_latency_ms"] is not None


async def test_analytics_by_hour(client: AsyncClient, seed_trace) -> None:
    now = datetime.now(timezone.utc)
    started = now - timedelta(hours=1)
    await seed_trace(started_at=started, ended_at=started + timedelta(seconds=1))

    resp = await client.get(
        "/traces/analytics",
        params={
            "metric": "volume",
            "granularity": "hour",
            "started_after": (now - timedelta(hours=2)).isoformat(),
            "started_before": now.isoformat(),
        },
    )
    assert resp.status_code == 200
    buckets = resp.json()
    total = sum(b["trace_count"] for b in buckets)
    assert total >= 1


async def test_analytics_empty_date_range(client: AsyncClient, seed_trace) -> None:
    now = datetime.now(timezone.utc)
    far_future = now + timedelta(days=365)
    resp = await client.get(
        "/traces/analytics",
        params={
            "metric": "volume",
            "granularity": "day",
            "started_after": far_future.isoformat(),
            "started_before": (far_future + timedelta(days=1)).isoformat(),
        },
    )
    assert resp.status_code == 200
    assert resp.json() == []


async def test_analytics_tokens_cost(client: AsyncClient, seed_trace) -> None:
    now = datetime.now(timezone.utc)
    started = now - timedelta(hours=1)
    span = build_span_payload(
        started_at=started,
        ended_at=started + timedelta(seconds=1),
        model="gpt-4o",
        token_usage={"prompt_tokens": 100, "completion_tokens": 50},
        cost={"input": 0.01, "output": 0.02, "total": 0.03},
    )
    await seed_trace(started_at=started, ended_at=started + timedelta(seconds=2), spans=[span])

    resp = await client.get(
        "/traces/analytics",
        params={
            "metric": "tokens",
            "granularity": "day",
            "started_after": (now - timedelta(days=1)).isoformat(),
            "started_before": now.isoformat(),
        },
    )
    assert resp.status_code == 200
    buckets = resp.json()
    assert len(buckets) >= 1
    assert buckets[0]["total_tokens"] >= 150


async def test_analytics_errors(client: AsyncClient, seed_trace) -> None:
    now = datetime.now(timezone.utc)
    started = now - timedelta(hours=1)
    await seed_trace(status="ERROR", started_at=started, ended_at=started + timedelta(seconds=1))
    await seed_trace(status="COMPLETED", started_at=started, ended_at=started + timedelta(seconds=1))

    resp = await client.get(
        "/traces/analytics",
        params={
            "metric": "errors",
            "granularity": "day",
            "started_after": (now - timedelta(days=1)).isoformat(),
            "started_before": now.isoformat(),
        },
    )
    assert resp.status_code == 200
    buckets = resp.json()
    total_errors = sum(b["error_count"] for b in buckets)
    assert total_errors >= 1
