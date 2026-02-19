"""Pure domain entities for the Identity bounded context.

These models carry **no** infrastructure dependencies (no SQLAlchemy,
no FastAPI).  They are the canonical representation of users,
organizations, memberships, projects, and API keys.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.registry.constants import MembershipRole


class User(BaseModel):
    """A registered user linked to an external identity provider."""

    id: UUID
    external_id: str
    email: str
    display_name: str = ""
    avatar_url: str = ""
    created_at: datetime
    last_sign_in_at: datetime | None = None


class Organization(BaseModel):
    """A tenant account that owns projects and API keys."""

    id: UUID
    name: str = Field(min_length=1, max_length=255)
    slug: str = Field(max_length=128)
    created_at: datetime


class Membership(BaseModel):
    """A user's role within an organization."""

    id: UUID
    user_id: UUID
    org_id: UUID
    role: MembershipRole = MembershipRole.MEMBER
    created_at: datetime


class Project(BaseModel):
    """A workspace within an organization that groups traces and evals."""

    id: UUID
    org_id: UUID
    name: str = Field(min_length=1, max_length=255)
    description: str = ""
    created_at: datetime


class APIKey(BaseModel):
    """An authentication credential scoped to one project.

    The raw key is never persisted; only its SHA-256 hash is stored.
    ``key_prefix`` keeps the first 8 characters (e.g. ``otr_a1b2``)
    so that users can identify which key is which in the UI.
    """

    id: UUID
    org_id: UUID
    project_id: UUID
    key_hash: str
    key_prefix: str = Field(max_length=12)
    name: str = Field(min_length=1, max_length=255)
    is_active: bool = True
    created_at: datetime
    last_used_at: datetime | None = None
    created_by: UUID | None = None
