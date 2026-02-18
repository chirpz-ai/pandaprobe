"""App-level JWT issuer and validator.

Issues short-lived JWTs (signed with APP_SECRET_KEY) that protect
management APIs (organisations, projects, users).  These tokens are
separate from the external IdP tokens -- they represent an
authenticated Opentracer session.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

import jwt

from app.registry.exceptions import AuthenticationError
from app.registry.settings import settings

_ALGORITHM = "HS256"
_ISSUER = "opentracer"


def issue_app_token(user_id: UUID, email: str) -> str:
    """Create a signed app JWT for the given user.

    Returns:
        An encoded JWT string valid for ``APP_JWT_EXPIRY_HOURS``.
    """
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "email": email,
        "iss": _ISSUER,
        "iat": now,
        "exp": now + timedelta(hours=settings.APP_JWT_EXPIRY_HOURS),
    }
    return jwt.encode(payload, settings.APP_SECRET_KEY, algorithm=_ALGORITHM)


def decode_app_token(token: str) -> dict:
    """Validate and decode an app JWT.

    Returns:
        The decoded payload dict with ``sub``, ``email``, ``exp``, etc.

    Raises:
        AuthenticationError: If the token is invalid, expired, or tampered.
    """
    try:
        return jwt.decode(
            token,
            settings.APP_SECRET_KEY,
            algorithms=[_ALGORITHM],
            issuer=_ISSUER,
            options={"require": ["sub", "email", "exp"]},
        )
    except jwt.ExpiredSignatureError:
        raise AuthenticationError("Session token has expired.")
    except jwt.InvalidTokenError as exc:
        raise AuthenticationError(f"Invalid session token: {exc}")


def get_auth_adapter():
    """Return the configured auth adapter instance based on ``AUTH_PROVIDER``.

    Supported values: ``"supabase"`` (default), ``"firebase"``.
    """
    provider = settings.AUTH_PROVIDER.lower()
    if provider == "firebase":
        from app.infrastructure.auth.firebase import FirebaseAdapter

        return FirebaseAdapter()
    from app.infrastructure.auth.supabase import SupabaseAdapter

    return SupabaseAdapter()
