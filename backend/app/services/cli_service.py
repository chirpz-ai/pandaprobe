"""Orchestration for the CLI OAuth2 Authorization Code + PKCE login flow.

The ``pandaprobe auth login`` CLI obtains a 90-day data-plane API key
without the raw key ever touching the browser:

1. The web ``/cli-login`` page calls :meth:`CliAuthService.issue_code`
   (authenticated as the Firebase user) to mint a single-use ``code``
   bound to ``{user, org, project, code_challenge}`` and persisted in
   Redis with a short TTL. **No API key is created here.**
2. The CLI calls :meth:`CliAuthService.exchange` (no auth header — the
   ``code`` + ``code_verifier`` is the proof). The code is consumed
   atomically, the PKCE challenge is verified with a constant-time
   compare, and only then is the 90-day key minted and returned once.

Security: PKCE ``S256`` is mandatory, codes are single-use with a
~120s TTL, and neither the ``code_verifier`` nor the raw key is ever
logged.
"""

import base64
import hashlib
import hmac
import json
import secrets
from datetime import datetime, timezone
from uuid import UUID

import redis.asyncio as aioredis
from sqlalchemy.ext.asyncio import AsyncSession

from app.registry.exceptions import AuthenticationError, ValidationError
from app.services.identity_service import IdentityService

# Redis key namespace for single-use authorization codes.
_CODE_PREFIX = "cli:authcode:"
# Authorization code time-to-live, in seconds (single-use, short-lived).
_CODE_TTL_SECONDS = 120
# Bytes of entropy for the opaque authorization code (>= 32 per spec).
_CODE_RANDOM_BYTES = 32
# API key name column is String(255).
_MAX_KEY_NAME_LEN = 255
# The CLI is only permitted to mint a fixed 90-day key lifetime.
_ALLOWED_EXPIRES_DAYS = 90


def verify_pkce(verifier: str, challenge: str) -> bool:
    """Return True iff ``BASE64URL(SHA256(verifier)) == challenge``.

    Uses a constant-time comparison to avoid leaking timing information
    about the stored challenge.
    """
    digest = hashlib.sha256(verifier.encode()).digest()
    computed = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
    return hmac.compare_digest(computed, challenge)


def _key_name_from_label(label: str) -> str:
    """Derive a human-readable, revocation-friendly API key name from *label*."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    clean_label = (label or "cli").strip() or "cli"
    name = f"pandaprobe-cli — {clean_label} — {today}"
    return name[:_MAX_KEY_NAME_LEN]


class CliAuthService:
    """Issue and exchange single-use CLI authorization codes."""

    def __init__(self, redis_client: aioredis.Redis, session: AsyncSession) -> None:
        """Initialise with an async Redis client and database session."""
        self._redis = redis_client
        self._session = session
        self._identity = IdentityService(session)

    async def issue_code(
        self,
        *,
        user_id: UUID,
        org_id: UUID,
        project_id: UUID,
        code_challenge: str,
        code_challenge_method: str,
        label: str,
        expires_days: int = 90,
    ) -> tuple[str, int]:
        """Mint a single-use authorization code bound to the PKCE challenge.

        Verifies the caller is a member of the org and that the project
        belongs to it, then stores the binding in Redis with a short TTL.
        Does **not** create an API key.

        Returns:
            A tuple of ``(code, expires_in_seconds)``.
        """
        if code_challenge_method != "S256":
            raise ValidationError("Unsupported code_challenge_method. Only 'S256' is allowed.")
        if not code_challenge or not code_challenge.strip():
            raise ValidationError("code_challenge is required.")
        if expires_days != _ALLOWED_EXPIRES_DAYS:
            raise ValidationError(f"Only a {_ALLOWED_EXPIRES_DAYS}-day key lifetime is supported for the CLI.")

        # Authorization: caller must belong to the org, and the project must be in it.
        await self._identity.require_membership(user_id, org_id)
        project = await self._identity.get_project(project_id, org_id=org_id)

        code = secrets.token_urlsafe(_CODE_RANDOM_BYTES)
        payload = {
            "user_id": str(user_id),
            "org_id": str(org_id),
            "project_id": str(project.id),
            "project_name": project.name,
            "code_challenge": code_challenge,
            "label": label,
            "expires_days": expires_days,
        }
        await self._redis.setex(f"{_CODE_PREFIX}{code}", _CODE_TTL_SECONDS, json.dumps(payload))
        return code, _CODE_TTL_SECONDS

    async def exchange(self, *, code: str, code_verifier: str) -> dict:
        """Exchange a single-use code + PKCE verifier for a fresh 90-day API key.

        The code is consumed atomically (single-use). The PKCE challenge
        is verified with a constant-time compare. The raw key is returned
        exactly once and is never persisted or logged.

        Raises:
            AuthenticationError: if the code is missing/expired/used, or
                the verifier does not match the stored challenge.
            AuthorizationError: if the user is no longer a member of the
                org by the time the code is exchanged.
        """
        if not code or not code_verifier:
            raise ValidationError("Both 'code' and 'code_verifier' are required.")

        # Atomic single-use: fetch-and-delete so a replay finds nothing.
        raw = await self._redis.getdel(f"{_CODE_PREFIX}{code}")
        if raw is None:
            raise AuthenticationError("Authorization code is invalid, expired, or already used.")

        payload = json.loads(raw)

        if not verify_pkce(code_verifier, payload["code_challenge"]):
            raise AuthenticationError("PKCE verification failed.")

        org_id = UUID(payload["org_id"])
        user_id = UUID(payload["user_id"])

        # Re-verify membership at exchange time
        await self._identity.require_membership(user_id, org_id)

        expiration = f"{int(payload['expires_days'])}d"
        api_key, raw_key = await self._identity.create_api_key(
            org_id=org_id,
            name=_key_name_from_label(payload["label"]),
            created_by=user_id,
            expiration=expiration,
        )

        return {
            "api_key": raw_key,
            "project_name": payload["project_name"],
            "org_id": str(org_id),
            "user_id": str(user_id),
            "key_id": str(api_key.id),
            "key_prefix": api_key.key_prefix,
            "expires_at": api_key.expires_at.isoformat() if api_key.expires_at else None,
        }
