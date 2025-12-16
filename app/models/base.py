"""Base models and common imports for all models."""

from datetime import datetime, UTC
from typing import List, Optional
from sqlmodel import Field, SQLModel, Relationship


class BaseModel(SQLModel):
    """Base model with common fields."""

    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
