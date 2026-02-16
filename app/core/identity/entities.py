"""Pure domain entities for the Identity bounded context.

These models carry **no** infrastructure dependencies (no SQLAlchemy,
no FastAPI).  They are the canonical representation of an Organisation
and its API keys within the core domain.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class Organization(BaseModel):
    """A tenant account that owns traces and API keys."""

    id: UUID
    name: str = Field(min_length=1, max_length=255)
    created_at: datetime


class APIKey(BaseModel):
    """An authentication credential belonging to an Organisation.

    The raw key is never persisted; only its SHA-256 hash is stored.
    ``key_prefix`` keeps the first 8 characters (e.g. ``otr_a1b2``)
    so that users can identify which key is which in the UI.
    """

    id: UUID
    org_id: UUID
    key_hash: str
    key_prefix: str = Field(max_length=12)
    name: str = Field(min_length=1, max_length=255)
    is_active: bool = True
    created_at: datetime
    last_used_at: datetime | None = None
