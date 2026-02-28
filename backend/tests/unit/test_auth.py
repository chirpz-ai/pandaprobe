"""Unit tests for the auth adapter infrastructure."""

from app.infrastructure.auth.adapters import get_auth_adapter
from app.infrastructure.auth.base import AuthAdapter, AuthClaims


def test_auth_claims_model() -> None:
    claims = AuthClaims(sub="abc-123", email="user@example.com", display_name="Test User")
    assert claims.sub == "abc-123"
    assert claims.email == "user@example.com"
    assert claims.display_name == "Test User"


def test_auth_claims_defaults() -> None:
    claims = AuthClaims(sub="id", email="a@b.com")
    assert claims.display_name == ""


def test_get_auth_adapter_returns_supabase_by_default() -> None:
    from app.infrastructure.auth.supabase import SupabaseAdapter

    adapter = get_auth_adapter()
    assert isinstance(adapter, SupabaseAdapter)
    assert isinstance(adapter, AuthAdapter)
