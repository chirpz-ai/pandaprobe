"""Unit tests for identity domain logic (no database required)."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.core.billing.plans import MAX_OWNED_ORGS
from app.registry.exceptions import OrgLimitReachedError
from app.registry.security import generate_api_key, hash_api_key, key_prefix


def test_generate_api_key_format() -> None:
    key = generate_api_key()
    assert key.startswith("sk_pp_")
    assert len(key) == 6 + 64  # prefix + 32 bytes hex


def test_hash_api_key_deterministic() -> None:
    key = "sk_pp_abc123"
    h1 = hash_api_key(key)
    h2 = hash_api_key(key)
    assert h1 == h2
    assert len(h1) == 64  # SHA-256 hex digest


def test_key_prefix_extraction() -> None:
    key = "sk_pp_abcdef1234567890"
    prefix = key_prefix(key)
    assert prefix == "sk_pp_abcd"


# ---------------------------------------------------------------------------
# Organization ownership limit
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_organization_blocked_at_limit() -> None:
    """Creating an organization when the user already owns MAX_OWNED_ORGS should raise."""
    from app.services.identity_service import IdentityService

    mock_session = AsyncMock()
    svc = IdentityService(mock_session)

    svc._repo.count_user_owned_orgs = AsyncMock(return_value=MAX_OWNED_ORGS)

    with pytest.raises(OrgLimitReachedError):
        await svc.create_organization(name="Extra Org", owner_id=uuid4())


@pytest.mark.asyncio
async def test_create_organization_allowed_below_limit() -> None:
    """Creating an organization when below the limit should succeed."""
    from app.core.identity.entities import Organization
    from app.services.identity_service import IdentityService

    mock_session = AsyncMock()
    svc = IdentityService(mock_session)

    fake_org = Organization(id=uuid4(), name="New Org", created_at=datetime.now(timezone.utc))
    svc._repo.count_user_owned_orgs = AsyncMock(return_value=MAX_OWNED_ORGS - 1)
    svc._repo.create_organization = AsyncMock(return_value=fake_org)
    svc._repo.create_membership = AsyncMock()
    svc._billing_repo.create_subscription = AsyncMock(
        return_value=AsyncMock(current_period_start=None, current_period_end=None)
    )
    svc._billing_repo.create_usage_record = AsyncMock()

    result = await svc.create_organization(name="New Org", owner_id=uuid4())
    assert result.name == "New Org"
