"""Supabase auth adapter for cloud-hosted Supabase Auth.

Uses the Supabase Python SDK to verify access tokens issued by a
Supabase project.  Requires ``SUPABASE_URL`` and ``SUPABASE_KEY``
to be set in the environment.

``SUPABASE_KEY`` can be either:
- The **anon / publishable** key (recommended — least privilege)
- The **secret / service-role** key (works but grants extra privileges)

Token verification uses ``auth.get_user(token)`` which sends the
user's own JWT to the Supabase Auth API.  The anon key is sufficient
because the user's JWT authenticates the request.
"""

from __future__ import annotations

from supabase import Client, create_client

from app.infrastructure.auth.base import AuthAdapter, AuthClaims
from app.logging import logger
from app.registry.exceptions import AuthenticationError
from app.registry.settings import settings

_supabase_client: Client | None = None


def _ensure_client() -> Client:
    """Lazily initialise the Supabase client (once per process)."""
    global _supabase_client

    if _supabase_client is not None:
        return _supabase_client

    url = settings.SUPABASE_URL
    key = settings.SUPABASE_KEY

    if not url or not key:
        raise AuthenticationError(
            "SUPABASE_URL and SUPABASE_KEY must be configured."
        )

    _supabase_client = create_client(url, key)
    logger.info("supabase_client_initialized", url=url)
    return _supabase_client


class SupabaseAdapter(AuthAdapter):
    """Verify access tokens issued by Supabase Auth."""

    def verify_token(self, token: str) -> AuthClaims:
        """Validate a Supabase access token via ``auth.get_user()``.

        The user's own JWT is sent to the Supabase Auth API which
        validates it and returns user metadata.  This handles token
        expiry and revocation server-side.
        """
        client = _ensure_client()

        try:
            response = client.auth.get_user(token)
        except Exception as exc:
            raise AuthenticationError(f"Supabase token verification failed: {exc}")

        user = response.user
        if user is None:
            raise AuthenticationError("Invalid token: no user returned.")

        if not user.id:
            raise AuthenticationError("Invalid token: missing user ID.")
        if not user.email:
            raise AuthenticationError("Invalid token: missing email.")

        display_name = ""
        if user.user_metadata:
            display_name = user.user_metadata.get("full_name", "") or user.user_metadata.get("name", "")

        return AuthClaims(
            sub=user.id,
            email=user.email,
            display_name=display_name,
        )
