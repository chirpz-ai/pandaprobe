"""Connection-pool configuration for the application Redis pool.

The VPC path to Memorystore drops established sockets without either end
noticing.  ``redis.asyncio`` does not detect that on checkout -- ``is_connected``
only tests that a reader and writer *exist*, not that the transport is alive --
so the first command writes to a closed uvloop transport and raises
``RuntimeError: ... the handler is closed``.  That misses redis-py's ``OSError``
branch, and an unconfigured pool carries ``Retry(NoBackoff(), 0)``, so the error
reached callers as a 500 on whatever endpoint happened to touch the cache.
"""

from app.infrastructure.redis.client import redis_pool

_DEAD_TRANSPORT_MESSAGE = (
    "unable to perform operation on <TCPTransport closed=True reading=False 0x0>; the handler is closed"
)


def _build_connection():
    """Instantiate a pool connection without opening a socket."""
    return redis_pool.connection_class(**redis_pool.connection_kwargs)


def test_idle_connections_are_validated_before_reuse() -> None:
    """Redis needs the same guard ``pool_pre_ping`` gives the SQL engine."""
    interval = redis_pool.connection_kwargs["health_check_interval"]
    assert interval > 0
    # Short enough to catch a socket reaped between two bursts of traffic.
    assert interval <= 60


def test_tcp_keepalive_is_enabled() -> None:
    """Keepalive lets the kernel notice a peer that vanished mid-connection."""
    assert redis_pool.connection_kwargs["socket_keepalive"] is True


def test_pool_retries_at_least_once() -> None:
    """An unconfigured pool is ``Retry(NoBackoff(), 0)`` -- no second attempt."""
    assert _build_connection().retry._retries >= 1


async def test_dead_transport_error_recovers_instead_of_reaching_the_caller() -> None:
    """The closed-transport ``RuntimeError`` must be retried, not surfaced.

    Drives the real ``Retry`` object the pool builds, through redis-py's own
    ``call_with_retry``, with the failure hook it uses: drop the connection and
    re-raise anything absent from ``retry_on_error``.
    """
    conn = _build_connection()
    attempts = 0

    async def _send_command():
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise RuntimeError(_DEAD_TRANSPORT_MESSAGE)
        return "cached-subscription"

    async def _on_error(error: Exception) -> None:
        if not isinstance(error, tuple(conn.retry_on_error)):
            raise error

    assert await conn.retry.call_with_retry(_send_command, _on_error) == "cached-subscription"
    assert attempts == 2, "the command must be reissued on a fresh connection"
