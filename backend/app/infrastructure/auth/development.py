"""No-auth adapter for local development.

Returns fixed, deterministic claims for a development superuser
without contacting any external identity provider.  The adapter
is only activated when ``AUTH_ENABLED=false`` in a development
environment.
"""

from __future__ import annotations

from app.infrastructure.auth.base import AuthAdapter, AuthClaims

_DEV_CLAIMS = AuthClaims(
    sub="dev-local-user-00000000",
    email="dev@localhost",
    display_name="Local Developer",
)


class DevelopmentAdapter(AuthAdapter):
    """Auth adapter that bypasses JWT verification for local development."""

    def verify_token(self, token: str) -> AuthClaims:
        """Return fixed dev-user claims, ignoring the token entirely."""
        return _DEV_CLAIMS
