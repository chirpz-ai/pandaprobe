"""Integration tests for the CLI OAuth2 + PKCE login flow.

Exercises the full issue -> exchange path against a real database and
real Redis. B1 (``issue_code``) is driven through the service (it would
otherwise require a Firebase JWT); B2 (``exchange``) is driven through
the real HTTP endpoint, which needs no auth.
"""

import base64
import hashlib
import secrets

import pytest
import redis.asyncio as aioredis
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.db.repositories.identity_repo import IdentityRepository
from app.infrastructure.db.repositories.user_repo import UserRepository
from app.registry.constants import MembershipRole
from app.registry.security import hash_api_key
from app.registry.settings import settings
from app.services.cli_service import CliAuthService

from .conftest import TEST_ORG_ID, TEST_PROJECT_ID

pytestmark = pytest.mark.asyncio


def _pkce_pair() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    return verifier, challenge


async def _seed_member(db_session: AsyncSession):
    """Create a user with a membership in the seeded test org."""
    user, *_ = await UserRepository(db_session).upsert_user(
        external_id="cli-test-user",
        email="cli@example.com",
        display_name="CLI Tester",
    )
    await IdentityRepository(db_session).create_membership(user.id, TEST_ORG_ID, role=MembershipRole.OWNER)
    await db_session.commit()
    return user


async def _issue_code(db_session: AsyncSession, user_id, challenge: str) -> str:
    redis_client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    try:
        svc = CliAuthService(redis_client, db_session)
        code, expires_in = await svc.issue_code(
            user_id=user_id,
            org_id=TEST_ORG_ID,
            project_id=TEST_PROJECT_ID,
            code_challenge=challenge,
            code_challenge_method="S256",
            label="laptop",
            expires_days=90,
        )
        assert expires_in == 120
        return code
    finally:
        await redis_client.aclose()


async def test_exchange_returns_working_90d_key(client: AsyncClient, db_session: AsyncSession):
    user = await _seed_member(db_session)
    verifier, challenge = _pkce_pair()
    code = await _issue_code(db_session, user.id, challenge)

    resp = await client.post("/cli/auth/exchange", json={"code": code, "code_verifier": verifier})
    assert resp.status_code == 200, resp.text
    body = resp.json()

    assert body["api_key"].startswith("sk_pp_")
    assert body["project_name"] == "Test Project"
    assert body["org_id"] == str(TEST_ORG_ID)
    assert "endpoint" not in body
    assert body["key_prefix"] == body["api_key"][:10]
    assert body["expires_at"] is not None

    # The minted key is persisted, active, org-scoped, and has a 90-day expiry —
    # i.e. it resolves exactly as _resolve_api_key would for the data plane.
    stored = await IdentityRepository(db_session).get_api_key_by_hash(hash_api_key(body["api_key"]))
    assert stored is not None
    assert stored.org_id == TEST_ORG_ID
    assert stored.is_active is True
    assert stored.expires_at is not None
    assert stored.name.startswith("pandaprobe-cli — laptop — ")


async def test_exchange_is_single_use(client: AsyncClient, db_session: AsyncSession):
    user = await _seed_member(db_session)
    verifier, challenge = _pkce_pair()
    code = await _issue_code(db_session, user.id, challenge)

    first = await client.post("/cli/auth/exchange", json={"code": code, "code_verifier": verifier})
    assert first.status_code == 200

    replay = await client.post("/cli/auth/exchange", json={"code": code, "code_verifier": verifier})
    assert replay.status_code == 401


async def test_exchange_rejects_wrong_verifier(client: AsyncClient, db_session: AsyncSession):
    user = await _seed_member(db_session)
    _verifier, challenge = _pkce_pair()
    code = await _issue_code(db_session, user.id, challenge)

    resp = await client.post(
        "/cli/auth/exchange",
        json={"code": code, "code_verifier": "totally-wrong-verifier"},
    )
    assert resp.status_code == 401


async def test_exchange_rejects_unknown_code(client: AsyncClient):
    resp = await client.post(
        "/cli/auth/exchange",
        json={"code": "does-not-exist", "code_verifier": "whatever"},
    )
    assert resp.status_code == 401


async def test_exchange_rejects_user_removed_from_org_within_ttl(client: AsyncClient, db_session: AsyncSession):
    # Membership is checked at issue time; if the user is removed before exchanging,
    # the key must NOT be minted (otherwise they regain access for 90 days).
    user = await _seed_member(db_session)
    verifier, challenge = _pkce_pair()
    code = await _issue_code(db_session, user.id, challenge)

    await IdentityRepository(db_session).delete_membership(user.id, TEST_ORG_ID)
    await db_session.commit()

    resp = await client.post("/cli/auth/exchange", json={"code": code, "code_verifier": verifier})
    assert resp.status_code == 403

    # And no key was created as a side effect.
    keys = await IdentityRepository(db_session).list_api_keys(TEST_ORG_ID)
    assert keys == []
