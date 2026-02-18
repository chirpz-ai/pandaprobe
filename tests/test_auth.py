"""Unit tests for the auth infrastructure (no external services)."""

from uuid import uuid4

from app.infrastructure.auth.jwt import decode_app_token, issue_app_token


def test_issue_and_decode_app_token() -> None:
    user_id = uuid4()
    email = "test@example.com"
    token = issue_app_token(user_id, email)

    payload = decode_app_token(token)
    assert payload["sub"] == str(user_id)
    assert payload["email"] == email
    assert payload["iss"] == "opentracer"


def test_decode_invalid_token_raises() -> None:
    from app.registry.exceptions import AuthenticationError

    import pytest

    with pytest.raises(AuthenticationError):
        decode_app_token("not-a-real-token")


def test_get_auth_adapter_returns_supabase_by_default() -> None:
    from app.infrastructure.auth.jwt import get_auth_adapter
    from app.infrastructure.auth.supabase import SupabaseAdapter

    adapter = get_auth_adapter()
    assert isinstance(adapter, SupabaseAdapter)
