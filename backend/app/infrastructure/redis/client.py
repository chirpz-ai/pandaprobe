"""Async Redis connection pool for the FastAPI application.

Provides a module-level connection pool and a FastAPI dependency
that yields a Redis client per request.
"""

from collections.abc import AsyncGenerator

import redis.asyncio as aioredis

from app.registry.settings import settings

redis_pool = aioredis.ConnectionPool.from_url(
    settings.REDIS_URL,
    max_connections=20,
    decode_responses=True,
)


async def get_redis() -> AsyncGenerator[aioredis.Redis, None]:
    """Yield an async Redis client backed by the shared connection pool."""
    client = aioredis.Redis(connection_pool=redis_pool)
    try:
        yield client
    finally:
        await client.aclose()


async def close_redis_pool() -> None:
    """Drain the connection pool on application shutdown."""
    await redis_pool.aclose()
