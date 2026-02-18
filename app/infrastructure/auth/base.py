"""Auth adapter interface and shared types.

Every external identity provider (Supabase, Firebase, etc.) implements
``AuthAdapter``.  The adapter validates an external JWT and returns
an ``AuthClaims`` object that the rest of the system understands.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from pydantic import BaseModel


class AuthClaims(BaseModel):
    """Normalised claims extracted from an external identity JWT.

    ``sub`` is the unique user identifier from the IdP.  It becomes
    the primary key in the local ``users`` table.
    """

    sub: str
    email: str
    display_name: str = ""


class AuthAdapter(ABC):
    """Contract for validating external identity provider tokens."""

    @abstractmethod
    async def verify_token(self, token: str) -> AuthClaims:
        """Validate a JWT from the external IdP and return normalised claims.

        Raises:
            AuthenticationError: If the token is invalid, expired, or revoked.
        """
        ...
