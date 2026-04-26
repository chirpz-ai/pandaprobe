from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from uuid import UUID

import pytest
import structlog
from httpx import AsyncClient
from sqlalchemy import delete

from app.api.context import ApiContext, AuthMethod
from app.api.dependencies import get_api_context
from app.core.identity.entities import User
from app.infrastructure.db.models import (
    MembershipModel,
    OrganizationModel,
    SubscriptionModel,
    UsageRecordModel,
    UserModel,
)
from app.infrastructure.db.repositories.billing_repo import BillingRepository
from app.main import app
from app.registry.constants import MembershipRole, SubscriptionPlan, SubscriptionStatus
from app.registry.exceptions import QuotaExceededError
from app.services.identity_service import IdentityService

from .conftest import TEST_ORG_ID

TEST_USER_ID = UUID("00000000-0000-4000-a000-000000000010")
TEST_USER_B_ID = UUID("00000000-0000-4000-a000-000000000011")
TEST_USER_C_ID = UUID("00000000-0000-4000-a000-000000000012")
TEST_ORG_B_ID = UUID("00000000-0000-4000-a000-000000000020")


@pytest.fixture(autouse=True)
def _jwt_user_context(test_org, test_project):
    user = User(
        id=TEST_USER_ID,
        external_id="test-sub-ext",
        email="sub-test@example.com",
        display_name="Sub Test",
        created_at=datetime.now(timezone.utc),
    )

    async def _get_api_context():
        return ApiContext.model_construct(
            request_id="test-request",
            auth_method=AuthMethod.JWT,
            organization=test_org,
            project=test_project,
            user=user,
            logger=structlog.get_logger(),
        )

    app.dependency_overrides[get_api_context] = _get_api_context
    yield


@pytest.fixture
async def seed_api_user(db_session):
    """Seed the JWT user + OWNER membership so org-scoped HTTP endpoints pass require_membership."""
    now = datetime.now(timezone.utc)
    db_session.add(
        UserModel(
            id=TEST_USER_ID,
            external_id="test-sub-ext",
            email="sub-test@example.com",
            display_name="Sub Test",
            created_at=now,
        )
    )
    db_session.add(
        MembershipModel(
            user_id=TEST_USER_ID,
            org_id=TEST_ORG_ID,
            role=MembershipRole.OWNER,
            created_at=now,
        )
    )
    await db_session.commit()


async def test_billing_repository_create_subscription_hobby(db_session, billing_isolated_org):
    repo = BillingRepository(db_session)
    sub = await repo.create_subscription(billing_isolated_org)
    await db_session.commit()
    assert sub.plan == SubscriptionPlan.HOBBY
    assert sub.status == SubscriptionStatus.ACTIVE
    assert sub.org_id == billing_isolated_org


async def test_billing_repository_get_subscription_by_org(db_session, billing_isolated_org):
    repo = BillingRepository(db_session)
    created = await repo.create_subscription(billing_isolated_org)
    await db_session.commit()
    fetched = await repo.get_subscription_by_org(billing_isolated_org)
    assert fetched is not None
    assert fetched.id == created.id


async def test_billing_repository_update_subscription(db_session, billing_isolated_org):
    repo = BillingRepository(db_session)
    await repo.create_subscription(billing_isolated_org)
    await db_session.commit()
    updated = await repo.update_subscription(billing_isolated_org, stripe_customer_id="cus_test123")
    assert updated is not None
    assert updated.stripe_customer_id == "cus_test123"
    await db_session.commit()


async def test_billing_repository_create_usage_record(db_session, billing_isolated_org):
    repo = BillingRepository(db_session)
    sub = await repo.create_subscription(billing_isolated_org)
    ps = sub.current_period_start
    pe = sub.current_period_end
    rec = await repo.create_usage_record(billing_isolated_org, ps, pe)
    await db_session.commit()
    assert rec.org_id == billing_isolated_org
    assert rec.period_start == ps


async def test_billing_repository_get_or_create_usage_record_idempotent(db_session, billing_isolated_org):
    repo = BillingRepository(db_session)
    sub = await repo.create_subscription(billing_isolated_org)
    ps = sub.current_period_start
    pe = sub.current_period_end
    a = await repo.get_or_create_usage_record(billing_isolated_org, ps, pe)
    b = await repo.get_or_create_usage_record(billing_isolated_org, ps, pe)
    await db_session.commit()
    assert a.id == b.id


async def test_billing_repository_upsert_usage_counters(db_session, billing_isolated_org):
    repo = BillingRepository(db_session)
    sub = await repo.create_subscription(billing_isolated_org)
    ps = sub.current_period_start
    pe = sub.current_period_end
    await repo.upsert_usage_counters(
        billing_isolated_org,
        ps,
        pe,
        trace_count=7,
        trace_eval_count=3,
        session_eval_count=2,
    )
    await db_session.commit()
    row = await repo.get_current_usage_record(billing_isolated_org, ps)
    assert row is not None
    assert row.trace_count == 7
    assert row.trace_eval_count == 3
    assert row.session_eval_count == 2


async def test_billing_repository_mark_billed(db_session, billing_isolated_org):
    repo = BillingRepository(db_session)
    sub = await repo.create_subscription(billing_isolated_org)
    ps = sub.current_period_start
    pe = sub.current_period_end
    await repo.create_usage_record(billing_isolated_org, ps, pe)
    await repo.mark_billed(billing_isolated_org, ps, "in_123")
    await db_session.commit()
    row = await repo.get_current_usage_record(billing_isolated_org, ps)
    assert row is not None
    assert row.billed is True
    assert row.stripe_invoice_id == "in_123"


async def test_billing_repository_advance_period(db_session, billing_isolated_org):
    repo = BillingRepository(db_session)
    sub = await repo.create_subscription(billing_isolated_org)
    new_start = sub.current_period_start + timedelta(days=30)
    new_end = sub.current_period_end + timedelta(days=30)
    await repo.advance_period(billing_isolated_org, new_start, new_end)
    await db_session.commit()
    s = await repo.get_subscription_by_org(billing_isolated_org)
    assert s is not None
    assert s.current_period_start == new_start
    assert s.current_period_end == new_end


async def test_billing_repository_list_hobby_subscriptions_due_for_reset(db_session, billing_isolated_org):
    repo = BillingRepository(db_session)
    past = datetime.now(timezone.utc) - timedelta(days=1)
    period_end = past
    period_start = past - timedelta(days=30)
    await repo.create_subscription(
        billing_isolated_org,
        period_start=period_start,
        period_end=period_end,
    )
    await db_session.commit()
    due = await repo.list_hobby_subscriptions_due_for_reset(datetime.now(timezone.utc))
    assert len(due) == 1
    assert due[0].org_id == billing_isolated_org


async def test_billing_repository_list_paid_subscriptions_active_excludes_hobby(db_session, billing_isolated_org):
    repo = BillingRepository(db_session)
    await db_session.execute(delete(UsageRecordModel).where(UsageRecordModel.org_id == TEST_ORG_ID))
    await db_session.execute(delete(SubscriptionModel).where(SubscriptionModel.org_id == TEST_ORG_ID))
    now = datetime.now(timezone.utc)
    db_session.add(OrganizationModel(id=TEST_ORG_B_ID, name="Org B", created_at=now))
    await repo.create_subscription(billing_isolated_org, plan=SubscriptionPlan.HOBBY)
    await repo.create_subscription(
        TEST_ORG_B_ID,
        plan=SubscriptionPlan.PRO,
        stripe_customer_id="cus_b",
        stripe_subscription_id="sub_b",
    )
    await db_session.commit()
    paid = await repo.list_paid_subscriptions_active()
    assert len(paid) == 1
    assert paid[0].plan == SubscriptionPlan.PRO


async def test_billing_repository_count_org_members(db_session):
    repo = BillingRepository(db_session)
    now = datetime.now(timezone.utc)
    db_session.add(UserModel(id=TEST_USER_ID, external_id="u1", email="u1@x.com", display_name="U1", created_at=now))
    db_session.add(UserModel(id=TEST_USER_B_ID, external_id="u2", email="u2@x.com", display_name="U2", created_at=now))
    db_session.add(
        MembershipModel(
            user_id=TEST_USER_ID,
            org_id=TEST_ORG_ID,
            role=MembershipRole.OWNER,
            created_at=now,
        )
    )
    db_session.add(
        MembershipModel(
            user_id=TEST_USER_B_ID,
            org_id=TEST_ORG_ID,
            role=MembershipRole.MEMBER,
            created_at=now,
        )
    )
    await db_session.commit()
    assert await repo.count_org_members(TEST_ORG_ID) == 2


async def test_get_subscription_returns_subscription_when_present(client: AsyncClient, seed_api_user):
    resp = await client.get(f"/organizations/{TEST_ORG_ID}/subscriptions")
    assert resp.status_code == 200
    data = resp.json()
    assert data["org_id"] == str(TEST_ORG_ID)
    assert data["plan"] == "PRO"


async def test_get_subscription_usage_returns_usage_snapshot(client: AsyncClient, seed_api_user):
    resp = await client.get(f"/organizations/{TEST_ORG_ID}/subscriptions/usage")
    assert resp.status_code == 200
    data = resp.json()
    assert data["plan"] == "PRO"
    assert "limits" in data
    assert data["limits"]["max_members"] == 2


async def test_get_subscription_returns_404_without_subscription(client: AsyncClient, db_session, seed_api_user):
    await db_session.execute(delete(UsageRecordModel).where(UsageRecordModel.org_id == TEST_ORG_ID))
    await db_session.execute(delete(SubscriptionModel).where(SubscriptionModel.org_id == TEST_ORG_ID))
    await db_session.commit()
    resp = await client.get(f"/organizations/{TEST_ORG_ID}/subscriptions")
    assert resp.status_code == 404


def _seed_user(db_session, uid: UUID, email: str) -> None:
    now = datetime.now(timezone.utc)
    db_session.add(UserModel(id=uid, external_id=f"ext-{uid}", email=email, display_name="U", created_at=now))


@patch("resend.Emails.send", return_value={"id": "mock_email_id"})
async def test_identity_hobby_blocks_adding_second_member(_mock_resend, db_session):
    repo = BillingRepository(db_session)
    await repo.update_subscription(TEST_ORG_ID, plan=SubscriptionPlan.HOBBY.value, stripe_subscription_id=None)
    now = datetime.now(timezone.utc)
    _seed_user(db_session, TEST_USER_ID, "owner@x.com")
    _seed_user(db_session, TEST_USER_B_ID, "member@x.com")
    db_session.add(
        MembershipModel(user_id=TEST_USER_ID, org_id=TEST_ORG_ID, role=MembershipRole.OWNER, created_at=now)
    )
    await db_session.commit()
    svc = IdentityService(db_session)
    with pytest.raises(QuotaExceededError):
        await svc.create_invitation(TEST_USER_ID, TEST_ORG_ID, "member@x.com", MembershipRole.MEMBER)


@patch("resend.Emails.send", return_value={"id": "mock_email_id"})
async def test_identity_pro_allows_two_members_blocks_third(_mock_resend, db_session):
    repo = BillingRepository(db_session)
    await repo.update_subscription(TEST_ORG_ID, plan=SubscriptionPlan.PRO.value, stripe_subscription_id="sub_x")
    now = datetime.now(timezone.utc)
    _seed_user(db_session, TEST_USER_ID, "owner@x.com")
    _seed_user(db_session, TEST_USER_B_ID, "m1@x.com")
    _seed_user(db_session, TEST_USER_C_ID, "m2@x.com")
    db_session.add(
        MembershipModel(user_id=TEST_USER_ID, org_id=TEST_ORG_ID, role=MembershipRole.OWNER, created_at=now)
    )
    await db_session.commit()
    svc = IdentityService(db_session)
    await svc.create_invitation(TEST_USER_ID, TEST_ORG_ID, "m1@x.com", MembershipRole.MEMBER)
    await db_session.commit()
    with pytest.raises(QuotaExceededError):
        await svc.create_invitation(TEST_USER_ID, TEST_ORG_ID, "m2@x.com", MembershipRole.MEMBER)
