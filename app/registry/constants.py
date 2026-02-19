"""Application-wide constants and enumerations.

Enums in this module follow OpenTelemetry naming conventions where
applicable so that exported data can be correlated with OTel tooling.
"""

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


class MembershipRole(StrEnum):
    """Role a user holds within an organization."""

    OWNER = "OWNER"
    ADMIN = "ADMIN"
    MEMBER = "MEMBER"


# Prefix prepended to every generated API key.
API_KEY_PREFIX = "otr_"

# Length of the random portion of an API key (bytes, hex-encoded).
API_KEY_RANDOM_BYTES = 32
