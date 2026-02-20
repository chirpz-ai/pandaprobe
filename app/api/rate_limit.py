"""Identity-aware rate limiting using slowapi.

The key function extracts a caller identity from request headers
(Bearer token hash or API key hash) so that rate limits are applied
per-identity rather than per-IP, which is more accurate for
multi-tenant SaaS behind shared proxies or load balancers.
"""

import hashlib

from slowapi import Limiter
from starlette.requests import Request

from app.registry.settings import settings


def _identity_key(request: Request) -> str:
    """Derive a rate-limit key from the caller's credential.

    Falls back to the client IP when no credential header is present
    (e.g. unauthenticated endpoints like /health).
    """
    auth = request.headers.get("Authorization", "")
    if auth.lower().startswith("bearer "):
        token = auth.split(None, 1)[1]
        return f"jwt:{hashlib.sha256(token.encode()).hexdigest()[:16]}"

    api_key = request.headers.get("X-API-Key", "")
    if api_key:
        return f"key:{hashlib.sha256(api_key.encode()).hexdigest()[:16]}"

    return f"ip:{request.client.host}" if request.client else "ip:unknown"


limiter = Limiter(
    key_func=_identity_key,
    default_limits=[settings.RATE_LIMIT_DEFAULT],
    storage_uri=settings.REDIS_URL,
)
