"""Async Redis connection pool for the FastAPI application.

Provides a module-level connection pool and a FastAPI dependency
that yields a Redis client per request.
"""

from collections.abc import AsyncGenerator

import redis.asyncio as aioredis
from redis.asyncio.retry import Retry
from redis.backoff import ExponentialBackoff
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import TimeoutError as RedisTimeoutError

from app.registry.settings import settings

#: Validate idle connections before reuse so stale sockets reconnect transparently.
_HEALTH_CHECK_INTERVAL_S = 30

_CONNECT_TIMEOUT_S = 5
_SOCKET_TIMEOUT_S = 5

#: uvloop reports closed transports as RuntimeError, which redis-py does not
#: retry by default.
_RETRYABLE_ERRORS = (RedisConnectionError, RedisTimeoutError, RuntimeError)

redis_pool = aioredis.ConnectionPool.from_url(
    settings.REDIS_URL,
    max_connections=20,
    decode_responses=True,
    health_check_interval=_HEALTH_CHECK_INTERVAL_S,
    socket_keepalive=True,
    socket_connect_timeout=_CONNECT_TIMEOUT_S,
    socket_timeout=_SOCKET_TIMEOUT_S,
    retry=Retry(ExponentialBackoff(cap=0.5, base=0.05), retries=1),
    retry_on_error=list(_RETRYABLE_ERRORS),
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
