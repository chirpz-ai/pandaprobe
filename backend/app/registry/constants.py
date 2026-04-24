"""Application-wide constants and enumerations.

Enums in this module follow OpenTelemetry naming conventions where
applicable so that exported data can be correlated with OTel tooling.
"""

import re
from enum import StrEnum


class SpanKind(StrEnum):
    """Categorises what a span represents in an agentic workflow."""

    AGENT = "AGENT"
    TOOL = "TOOL"
    LLM = "LLM"
    RETRIEVER = "RETRIEVER"
    CHAIN = "CHAIN"
    EMBEDDING = "EMBEDDING"
    OTHER = "OTHER"


class SpanStatusCode(StrEnum):
    """Mirrors the OTel StatusCode for a span's outcome."""

    UNSET = "UNSET"
    OK = "OK"
    ERROR = "ERROR"


class TraceStatus(StrEnum):
    """High-level status of a trace."""

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    ERROR = "ERROR"


class EvaluationStatus(StrEnum):
    """Lifecycle status of an evaluation job."""

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class ScoreSource(StrEnum):
    """Who produced the score judgment (not how it arrived).

    AUTOMATED -- the eval system's LLM judge produced this score
    ANNOTATION -- a human assigned this score manually
    PROGRAMMATIC -- external code submitted this score via API/SDK
    """

    AUTOMATED = "AUTOMATED"
    ANNOTATION = "ANNOTATION"
    PROGRAMMATIC = "PROGRAMMATIC"


class ScoreStatus(StrEnum):
    """Outcome of a trace score evaluation attempt."""

    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    PENDING = "PENDING"


class ScoreDataType(StrEnum):
    """Data type for a trace score value."""

    NUMERIC = "NUMERIC"
    BOOLEAN = "BOOLEAN"
    CATEGORICAL = "CATEGORICAL"


class MembershipRole(StrEnum):
    """Role a user holds within an organization."""

    OWNER = "OWNER"
    ADMIN = "ADMIN"
    MEMBER = "MEMBER"


class InvitationStatus(StrEnum):
    """Lifecycle status of an organization invitation."""

    PENDING = "PENDING"
    ACCEPTED = "ACCEPTED"
    DECLINED = "DECLINED"
    REVOKED = "REVOKED"
    EXPIRED = "EXPIRED"


class TraceSortBy(StrEnum):
    """Columns available for sorting trace list results."""

    STARTED_AT = "started_at"
    ENDED_AT = "ended_at"
    NAME = "name"
    LATENCY = "latency"
    STATUS = "status"


class SortOrder(StrEnum):
    """Generic ascending / descending sort direction."""

    ASC = "asc"
    DESC = "desc"


class AnalyticsMetric(StrEnum):
    """Available metric types for the analytics endpoint."""

    VOLUME = "volume"
    ERRORS = "errors"
    LATENCY = "latency"
    COST = "cost"
    TOKENS = "tokens"
    MODELS = "models"


class SessionSortBy(StrEnum):
    """Columns available for sorting session list results."""

    RECENT = "recent"
    TRACE_COUNT = "trace_count"
    LATENCY = "latency"
    COST = "cost"


class AnalyticsGranularity(StrEnum):
    """Time-bucket granularity for analytics queries."""

    HOUR = "hour"
    DAY = "day"
    WEEK = "week"


class MonitorStatus(StrEnum):
    """Lifecycle status of an evaluation monitor."""

    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"


class MonitorCadence(StrEnum):
    """Predefined cadence intervals for evaluation monitors."""

    EVERY_6H = "every_6h"
    DAILY = "daily"
    WEEKLY = "weekly"
    CUSTOM = "custom"


class SubscriptionPlan(StrEnum):
    """Tier of an organization's subscription."""

    HOBBY = "HOBBY"
    PRO = "PRO"
    STARTUP = "STARTUP"
    ENTERPRISE = "ENTERPRISE"
    DEVELOPMENT = "DEVELOPMENT"


class SubscriptionStatus(StrEnum):
    """Lifecycle status of a Stripe-backed subscription."""

    ACTIVE = "ACTIVE"
    PAST_DUE = "PAST_DUE"
    CANCELED = "CANCELED"
    INCOMPLETE = "INCOMPLETE"


class UsageCategory(StrEnum):
    """Billable usage categories tracked per billing period."""

    TRACES = "traces"
    TRACE_EVALS = "trace_evals"
    SESSION_EVALS = "session_evals"


# Prefix prepended to every generated API key.
API_KEY_PREFIX = "sk_pp_"

# Length of the random portion of an API key (bytes, hex-encoded).
API_KEY_RANDOM_BYTES = 32

# ---------------------------------------------------------------------------
# Billing / Redis key constants
# ---------------------------------------------------------------------------

SUB_CACHE_PREFIX = "pp:sub:"
SUB_CACHE_TTL = 300  # seconds (5 minutes)
USAGE_KEY_PREFIX = "pp:usage:"
USAGE_KEY_BUFFER_DAYS = 7
OVERAGE_LOCK_PREFIX = "pp:overage_lock:"
OVERAGE_LOCK_TTL = 60  # seconds

# ---------------------------------------------------------------------------
# Resource name validation
# ---------------------------------------------------------------------------

_SAFE_NAME_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9 _.'-]{0,253}[a-zA-Z0-9]$")
_MAX_NAME_LEN = 255
_CONTROL_CHAR_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def validate_resource_name(value: str, label: str = "Name") -> str:
    """Sanitize and validate a user-supplied resource name.

    Allowed characters: letters, digits, spaces, hyphens, underscores,
    dots, and apostrophes.  Must start and end with an alphanumeric
    character and be 1–255 characters long.

    Returns the stripped name on success; raises ``ValueError`` with a
    human-readable message on failure.
    """
    name = value.strip()
    if not name:
        raise ValueError(f"{label} must not be empty.")
    if len(name) > _MAX_NAME_LEN:
        raise ValueError(f"{label} must be at most {_MAX_NAME_LEN} characters.")
    if len(name) == 1:
        if not name.isalnum():
            raise ValueError(f"{label} must start and end with a letter or digit.")
        return name
    if not _SAFE_NAME_RE.match(name):
        raise ValueError(
            f"{label} must start and end with a letter or digit and contain "
            f"only letters, digits, spaces, hyphens, underscores, dots, or apostrophes."
        )
    return name


def sanitize_text(value: str, label: str = "Field", *, max_length: int = 2000) -> str:
    r"""Sanitize a free-text field (e.g. descriptions, notes).

    Strips leading/trailing whitespace, rejects control characters
    (except ``\n`` and ``\t``), and enforces a maximum length.

    Returns the cleaned string; raises ``ValueError`` on failure.
    """
    text = value.strip()
    if len(text) > max_length:
        raise ValueError(f"{label} must be at most {max_length} characters.")
    if _CONTROL_CHAR_RE.search(text):
        raise ValueError(f"{label} contains invalid control characters.")
    return text
