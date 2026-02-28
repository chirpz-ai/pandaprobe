"""Shared response schemas used across multiple route modules."""

from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    """Wrapper for paginated list endpoints.

    Provides the total count alongside the page of items so that
    clients (dashboards, SDKs) can render pagination controls.
    """

    items: list[T]
    total: int
    limit: int
    offset: int
