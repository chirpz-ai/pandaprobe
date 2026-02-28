"""Domain exception hierarchy for PandaProbe.

Every exception in this module maps to a specific HTTP status code so
that the API layer can translate them uniformly.
"""


class PandaProbeError(Exception):
    """Base class for all PandaProbe domain errors."""

    status_code: int = 500
    detail: str = "An unexpected error occurred."

    def __init__(self, detail: str | None = None) -> None:
        """Override detail message if provided, otherwise use the class default."""
        self.detail = detail or self.__class__.detail
        super().__init__(self.detail)


class NotFoundError(PandaProbeError):
    """Raised when a requested resource does not exist."""

    status_code = 404
    detail = "Resource not found."


class AuthenticationError(PandaProbeError):
    """Raised when an API key is missing or invalid."""

    status_code = 401
    detail = "Invalid or missing API key."


class AuthorizationError(PandaProbeError):
    """Raised when the caller lacks permission for an action."""

    status_code = 403
    detail = "Insufficient permissions."


class ConflictError(PandaProbeError):
    """Raised on uniqueness or state-conflict violations."""

    status_code = 409
    detail = "Resource conflict."


class ValidationError(PandaProbeError):
    """Raised when domain validation fails outside of Pydantic."""

    status_code = 422
    detail = "Validation error."
