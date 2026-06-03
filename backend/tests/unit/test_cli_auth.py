"""Unit tests for the CLI auth PKCE helpers (no infra required)."""

import base64
import hashlib
import secrets
from uuid import uuid4

import pytest

from app.registry.exceptions import ValidationError
from app.services.cli_service import CliAuthService, _key_name_from_label, verify_pkce


def _challenge_for(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode()).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode()


def test_verify_pkce_matches_correct_verifier():
    verifier = secrets.token_urlsafe(64)
    challenge = _challenge_for(verifier)
    assert verify_pkce(verifier, challenge) is True


def test_verify_pkce_rejects_wrong_verifier():
    challenge = _challenge_for(secrets.token_urlsafe(64))
    assert verify_pkce("not-the-verifier", challenge) is False


def test_verify_pkce_rejects_padded_challenge():
    # The S256 challenge is base64url *without* padding; a padded value must not match.
    verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(verifier.encode()).digest()
    padded = base64.urlsafe_b64encode(digest).decode()  # keeps '=' padding
    assert verify_pkce(verifier, padded) is False


def test_key_name_from_label_format():
    name = _key_name_from_label("my-laptop")
    assert name.startswith("pandaprobe-cli — my-laptop — ")
    # Trailing date segment YYYY-MM-DD.
    assert name.split(" — ")[-1].count("-") == 2


def test_key_name_from_label_blank_falls_back():
    assert _key_name_from_label("   ").startswith("pandaprobe-cli — cli — ")


def test_key_name_from_label_truncated_to_255():
    name = _key_name_from_label("x" * 500)
    assert len(name) <= 255


@pytest.mark.asyncio
@pytest.mark.parametrize("bad_days", [30, 60, 91, 365, 0])
async def test_issue_code_rejects_non_90_day_lifetime(bad_days):
    # The lifetime check runs before any DB/Redis access, so None deps are fine here.
    svc = CliAuthService(None, None)  # type: ignore[arg-type]
    with pytest.raises(ValidationError, match="90-day"):
        await svc.issue_code(
            user_id=uuid4(),
            org_id=uuid4(),
            project_id=uuid4(),
            code_challenge="some-challenge",
            code_challenge_method="S256",
            label="laptop",
            expires_days=bad_days,
        )
