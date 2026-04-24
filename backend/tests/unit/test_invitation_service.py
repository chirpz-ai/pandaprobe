"""Unit tests for invitation domain logic (no database required)."""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from app.core.identity.entities import Invitation, Membership, User
from app.registry.constants import InvitationStatus, MembershipRole
from app.registry.exceptions import AuthorizationError, ConflictError, NotFoundError, QuotaExceededError


def _make_user(*, email: str = "actor@example.com", user_id=None) -> User:
    return User(
        id=user_id or uuid4(),
        external_id="ext-1",
        email=email,
        display_name="Actor",
        created_at=datetime.now(timezone.utc),
    )


def _make_membership(*, user_id=None, org_id=None, role=MembershipRole.OWNER) -> Membership:
    return Membership(
        id=uuid4(),
        user_id=user_id or uuid4(),
        org_id=org_id or uuid4(),
        role=role,
        created_at=datetime.now(timezone.utc),
    )


def _make_invitation(
    *,
    org_id=None,
    email="invitee@example.com",
    status=InvitationStatus.PENDING,
    expires_at=None,
) -> Invitation:
    return Invitation(
        id=uuid4(),
        org_id=org_id or uuid4(),
        email=email,
        role=MembershipRole.MEMBER,
        invited_by=uuid4(),
        status=status,
        created_at=datetime.now(timezone.utc),
        expires_at=expires_at or (datetime.now(timezone.utc) + timedelta(days=7)),
        org_name="Test Org",
        inviter_display_name="Inviter",
        inviter_email="inviter@example.com",
    )


def _svc():
    from app.services.identity_service import IdentityService

    mock_session = AsyncMock()
    svc = IdentityService(mock_session)
    return svc


# ---------------------------------------------------------------------------
# create_invitation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_invitation_success() -> None:
    svc = _svc()
    actor_id = uuid4()
    org_id = uuid4()
    actor_user = _make_user(email="owner@example.com", user_id=actor_id)

    svc._repo.get_membership = AsyncMock(
        return_value=_make_membership(user_id=actor_id, org_id=org_id, role=MembershipRole.OWNER)
    )
    svc._user_repo.get_user = AsyncMock(return_value=actor_user)
    svc._user_repo.get_user_by_email = AsyncMock(return_value=None)
    svc._invitation_repo.get_pending_invitation = AsyncMock(return_value=None)
    svc._billing_repo.get_subscription_by_org = AsyncMock(return_value=None)
    svc._invitation_repo.create_invitation = AsyncMock(
        return_value=_make_invitation(org_id=org_id, email="new@example.com")
    )

    result = await svc.create_invitation(actor_id=actor_id, org_id=org_id, email="New@Example.com")
    assert result.email == "new@example.com"
    svc._invitation_repo.create_invitation.assert_awaited_once()


@pytest.mark.asyncio
async def test_create_invitation_member_cannot_invite() -> None:
    svc = _svc()
    actor_id = uuid4()
    org_id = uuid4()

    svc._repo.get_membership = AsyncMock(
        return_value=_make_membership(user_id=actor_id, org_id=org_id, role=MembershipRole.MEMBER)
    )

    with pytest.raises(AuthorizationError, match="Members cannot invite"):
        await svc.create_invitation(actor_id=actor_id, org_id=org_id, email="test@example.com")


@pytest.mark.asyncio
async def test_create_invitation_admin_can_only_invite_member() -> None:
    svc = _svc()
    actor_id = uuid4()
    org_id = uuid4()

    svc._repo.get_membership = AsyncMock(
        return_value=_make_membership(user_id=actor_id, org_id=org_id, role=MembershipRole.ADMIN)
    )

    with pytest.raises(AuthorizationError, match="Admins can only invite"):
        await svc.create_invitation(
            actor_id=actor_id, org_id=org_id, email="test@example.com", role=MembershipRole.ADMIN
        )


@pytest.mark.asyncio
async def test_create_invitation_cannot_invite_as_owner() -> None:
    svc = _svc()
    actor_id = uuid4()
    org_id = uuid4()

    svc._repo.get_membership = AsyncMock(
        return_value=_make_membership(user_id=actor_id, org_id=org_id, role=MembershipRole.OWNER)
    )

    with pytest.raises(AuthorizationError, match="Cannot invite a user as OWNER"):
        await svc.create_invitation(
            actor_id=actor_id, org_id=org_id, email="test@example.com", role=MembershipRole.OWNER
        )


@pytest.mark.asyncio
async def test_create_invitation_self_invite_rejected() -> None:
    svc = _svc()
    actor_id = uuid4()
    org_id = uuid4()
    actor_user = _make_user(email="me@example.com", user_id=actor_id)

    svc._repo.get_membership = AsyncMock(
        return_value=_make_membership(user_id=actor_id, org_id=org_id, role=MembershipRole.OWNER)
    )
    svc._user_repo.get_user = AsyncMock(return_value=actor_user)

    with pytest.raises(ConflictError, match="cannot invite yourself"):
        await svc.create_invitation(actor_id=actor_id, org_id=org_id, email="Me@Example.com")


@pytest.mark.asyncio
async def test_create_invitation_existing_member_rejected() -> None:
    svc = _svc()
    actor_id = uuid4()
    org_id = uuid4()
    existing_user_id = uuid4()
    actor_user = _make_user(email="owner@example.com", user_id=actor_id)
    existing_user = _make_user(email="existing@example.com", user_id=existing_user_id)

    svc._repo.get_membership = AsyncMock(
        side_effect=[
            _make_membership(user_id=actor_id, org_id=org_id, role=MembershipRole.OWNER),
            _make_membership(user_id=existing_user_id, org_id=org_id, role=MembershipRole.MEMBER),
        ]
    )
    svc._user_repo.get_user = AsyncMock(return_value=actor_user)
    svc._user_repo.get_user_by_email = AsyncMock(return_value=existing_user)

    with pytest.raises(ConflictError, match="already a member"):
        await svc.create_invitation(actor_id=actor_id, org_id=org_id, email="existing@example.com")


@pytest.mark.asyncio
async def test_create_invitation_duplicate_pending_rejected() -> None:
    svc = _svc()
    actor_id = uuid4()
    org_id = uuid4()
    actor_user = _make_user(email="owner@example.com", user_id=actor_id)

    svc._repo.get_membership = AsyncMock(
        return_value=_make_membership(user_id=actor_id, org_id=org_id, role=MembershipRole.OWNER)
    )
    svc._user_repo.get_user = AsyncMock(return_value=actor_user)
    svc._user_repo.get_user_by_email = AsyncMock(return_value=None)
    svc._invitation_repo.get_pending_invitation = AsyncMock(
        return_value=_make_invitation(org_id=org_id, email="dup@example.com")
    )

    with pytest.raises(ConflictError, match="already pending"):
        await svc.create_invitation(actor_id=actor_id, org_id=org_id, email="dup@example.com")


@pytest.mark.asyncio
async def test_create_invitation_quota_exceeded() -> None:
    svc = _svc()
    actor_id = uuid4()
    org_id = uuid4()
    actor_user = _make_user(email="owner@example.com", user_id=actor_id)

    svc._repo.get_membership = AsyncMock(
        return_value=_make_membership(user_id=actor_id, org_id=org_id, role=MembershipRole.OWNER)
    )
    svc._user_repo.get_user = AsyncMock(return_value=actor_user)
    svc._user_repo.get_user_by_email = AsyncMock(return_value=None)
    svc._invitation_repo.get_pending_invitation = AsyncMock(return_value=None)

    sub_mock = AsyncMock()
    sub_mock.plan = "PRO"
    svc._billing_repo.get_subscription_by_org = AsyncMock(return_value=sub_mock)
    svc._billing_repo.count_org_members = AsyncMock(return_value=1)
    svc._invitation_repo.count_pending_for_org = AsyncMock(return_value=1)

    with pytest.raises(QuotaExceededError):
        await svc.create_invitation(actor_id=actor_id, org_id=org_id, email="new@example.com")


@pytest.mark.asyncio
async def test_create_invitation_email_normalized_lowercase() -> None:
    svc = _svc()
    actor_id = uuid4()
    org_id = uuid4()
    actor_user = _make_user(email="owner@example.com", user_id=actor_id)

    svc._repo.get_membership = AsyncMock(
        return_value=_make_membership(user_id=actor_id, org_id=org_id, role=MembershipRole.OWNER)
    )
    svc._user_repo.get_user = AsyncMock(return_value=actor_user)
    svc._user_repo.get_user_by_email = AsyncMock(return_value=None)
    svc._invitation_repo.get_pending_invitation = AsyncMock(return_value=None)
    svc._billing_repo.get_subscription_by_org = AsyncMock(return_value=None)
    svc._invitation_repo.create_invitation = AsyncMock(
        return_value=_make_invitation(org_id=org_id, email="upper@example.com")
    )

    await svc.create_invitation(actor_id=actor_id, org_id=org_id, email="  UPPER@Example.COM  ")

    call_kwargs = svc._invitation_repo.create_invitation.call_args.kwargs
    assert call_kwargs["email"] == "upper@example.com"


# ---------------------------------------------------------------------------
# accept_invitation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_accept_invitation_success() -> None:
    svc = _svc()
    user_id = uuid4()
    org_id = uuid4()
    inv = _make_invitation(org_id=org_id, email="user@example.com")
    user = _make_user(email="user@example.com", user_id=user_id)

    svc._invitation_repo.get_invitation = AsyncMock(return_value=inv)
    svc._user_repo.get_user = AsyncMock(return_value=user)
    svc._repo.get_membership = AsyncMock(return_value=None)
    svc._repo.create_membership = AsyncMock(
        return_value=_make_membership(user_id=user_id, org_id=org_id, role=MembershipRole.MEMBER)
    )
    svc._invitation_repo.update_status = AsyncMock()

    result = await svc.accept_invitation(user_id=user_id, invitation_id=inv.id)
    assert result.role == MembershipRole.MEMBER
    svc._invitation_repo.update_status.assert_awaited_once_with(inv.id, InvitationStatus.ACCEPTED)


@pytest.mark.asyncio
async def test_accept_invitation_already_processed() -> None:
    svc = _svc()
    user_id = uuid4()
    inv = _make_invitation(status=InvitationStatus.ACCEPTED)
    user = _make_user(email=inv.email, user_id=user_id)

    svc._invitation_repo.get_invitation = AsyncMock(return_value=inv)
    svc._user_repo.get_user = AsyncMock(return_value=user)

    with pytest.raises(ConflictError, match="already been processed"):
        await svc.accept_invitation(user_id=user_id, invitation_id=inv.id)


@pytest.mark.asyncio
async def test_accept_invitation_expired() -> None:
    svc = _svc()
    user_id = uuid4()
    inv = _make_invitation(expires_at=datetime.now(timezone.utc) - timedelta(hours=1))
    user = _make_user(email=inv.email, user_id=user_id)

    svc._invitation_repo.get_invitation = AsyncMock(return_value=inv)
    svc._user_repo.get_user = AsyncMock(return_value=user)
    svc._invitation_repo.update_status = AsyncMock()

    with pytest.raises(ConflictError, match="expired"):
        await svc.accept_invitation(user_id=user_id, invitation_id=inv.id)

    svc._invitation_repo.update_status.assert_awaited_once_with(inv.id, InvitationStatus.EXPIRED)


@pytest.mark.asyncio
async def test_accept_invitation_email_mismatch() -> None:
    svc = _svc()
    user_id = uuid4()
    inv = _make_invitation(email="other@example.com")
    user = _make_user(email="me@example.com", user_id=user_id)

    svc._invitation_repo.get_invitation = AsyncMock(return_value=inv)
    svc._user_repo.get_user = AsyncMock(return_value=user)

    with pytest.raises(AuthorizationError, match="different email"):
        await svc.accept_invitation(user_id=user_id, invitation_id=inv.id)


@pytest.mark.asyncio
async def test_accept_invitation_already_a_member() -> None:
    svc = _svc()
    user_id = uuid4()
    org_id = uuid4()
    inv = _make_invitation(org_id=org_id, email="user@example.com")
    user = _make_user(email="user@example.com", user_id=user_id)

    svc._invitation_repo.get_invitation = AsyncMock(return_value=inv)
    svc._user_repo.get_user = AsyncMock(return_value=user)
    svc._repo.get_membership = AsyncMock(return_value=_make_membership(user_id=user_id, org_id=org_id))

    with pytest.raises(ConflictError, match="already a member"):
        await svc.accept_invitation(user_id=user_id, invitation_id=inv.id)


# ---------------------------------------------------------------------------
# decline_invitation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_decline_invitation_success() -> None:
    svc = _svc()
    user_id = uuid4()
    inv = _make_invitation(email="user@example.com")
    user = _make_user(email="user@example.com", user_id=user_id)

    svc._invitation_repo.get_invitation = AsyncMock(return_value=inv)
    svc._user_repo.get_user = AsyncMock(return_value=user)
    svc._invitation_repo.update_status = AsyncMock()

    await svc.decline_invitation(user_id=user_id, invitation_id=inv.id)
    svc._invitation_repo.update_status.assert_awaited_once_with(inv.id, InvitationStatus.DECLINED)


# ---------------------------------------------------------------------------
# revoke_invitation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_revoke_invitation_success() -> None:
    svc = _svc()
    actor_id = uuid4()
    org_id = uuid4()
    inv = _make_invitation(org_id=org_id)

    svc._invitation_repo.get_invitation = AsyncMock(return_value=inv)
    svc._repo.get_membership = AsyncMock(
        return_value=_make_membership(user_id=actor_id, org_id=org_id, role=MembershipRole.ADMIN)
    )
    svc._invitation_repo.update_status = AsyncMock()

    await svc.revoke_invitation(actor_id=actor_id, org_id=org_id, invitation_id=inv.id)
    svc._invitation_repo.update_status.assert_awaited_once_with(inv.id, InvitationStatus.REVOKED)


@pytest.mark.asyncio
async def test_revoke_invitation_not_pending() -> None:
    svc = _svc()
    actor_id = uuid4()
    org_id = uuid4()
    inv = _make_invitation(org_id=org_id, status=InvitationStatus.ACCEPTED)

    svc._invitation_repo.get_invitation = AsyncMock(return_value=inv)
    svc._repo.get_membership = AsyncMock(
        return_value=_make_membership(user_id=actor_id, org_id=org_id, role=MembershipRole.ADMIN)
    )

    with pytest.raises(ConflictError, match="pending"):
        await svc.revoke_invitation(actor_id=actor_id, org_id=org_id, invitation_id=inv.id)
