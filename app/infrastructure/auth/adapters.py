"""Auth adapter factory.

Returns the configured external identity provider adapter
(Supabase or Firebase) based on the ``AUTH_PROVIDER`` setting.
"""

from __future__ import annotations

from app.infrastructure.auth.base import AuthAdapter
from app.registry.settings import settings


def get_auth_adapter() -> AuthAdapter:
    """Return the configured auth adapter instance based on ``AUTH_PROVIDER``.

    Supported values: ``"supabase"`` (default), ``"firebase"``.
    """
    provider = settings.AUTH_PROVIDER.lower()
    if provider == "firebase":
        from app.infrastructure.auth.firebase import FirebaseAdapter

        return FirebaseAdapter()
    from app.infrastructure.auth.supabase import SupabaseAdapter

    return SupabaseAdapter()
