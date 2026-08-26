"""Replay-safe Redis lock operations."""

import redis.asyncio as aioredis

_COMPLETED_VALUE = "completed"

_ACQUIRE_LOCK_SCRIPT = """
local current = redis.call('GET', KEYS[1])
if current == ARGV[1] then
    return 1
end
if current then
    return 0
end
return redis.call('SET', KEYS[1], ARGV[1], 'NX', 'EX', ARGV[2]) and 1 or 0
"""

_RELEASE_LOCK_SCRIPT = """
if redis.call('GET', KEYS[1]) == ARGV[1] then
    return redis.call('DEL', KEYS[1])
end
return 0
"""

_COMPLETE_LOCK_SCRIPT = """
local current = redis.call('GET', KEYS[1])
if current == ARGV[1] then
    redis.call('SET', KEYS[1], ARGV[2], 'EX', ARGV[3])
    return 1
end
if current == ARGV[2] then
    return 1
end
return 0
"""


async def acquire_owned_lock(client: aioredis.Redis, key: str, token: str, *, ttl: int) -> bool:
    """Acquire a lock, treating a replay with the same token as successful."""
    return bool(await client.eval(_ACQUIRE_LOCK_SCRIPT, 1, key, token, ttl))


async def release_owned_lock(client: aioredis.Redis, key: str, token: str) -> None:
    """Release a lock only when it is still owned by ``token``."""
    await client.eval(_RELEASE_LOCK_SCRIPT, 1, key, token)


async def complete_owned_lock(client: aioredis.Redis, key: str, token: str, *, ttl: int) -> bool:
    """Replace an owned lock with a durable completion marker."""
    return bool(await client.eval(_COMPLETE_LOCK_SCRIPT, 1, key, token, _COMPLETED_VALUE, ttl))
