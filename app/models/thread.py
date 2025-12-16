"""This file contains the thread model for the application."""

from datetime import (
    UTC,
    datetime,
)

from sqlmodel import (
    Field,
    SQLModel,
)


class Thread(SQLModel, table=True):
    """Thread model for storing conversation threads.

    Attributes:
        id: The primary key
        created_at: When the thread was created
        messages: Relationship to messages in this thread
    """

    id: str = Field(primary_key=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
