"""SQLAlchemy ORM models for Opentracer.

All table definitions live here so that Alembic can discover them via
``Base.metadata`` for auto-generated migrations.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Index,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from app.registry.constants import SpanKind, SpanStatusCode, TraceStatus


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    """Shared declarative base for every ORM model."""

    pass


# ---------------------------------------------------------------------------
# Identity domain
# ---------------------------------------------------------------------------


class OrganizationModel(Base):
    """Tenant account."""

    __tablename__ = "organizations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)

    api_keys: Mapped[list["APIKeyModel"]] = relationship(back_populates="organization", cascade="all, delete-orphan")


class APIKeyModel(Base):
    """Hashed API key belonging to an organisation."""

    __tablename__ = "api_keys"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    key_hash: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    key_prefix: Mapped[str] = mapped_column(String(12), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    organization: Mapped["OrganizationModel"] = relationship(back_populates="api_keys")


# ---------------------------------------------------------------------------
# Traces domain
# ---------------------------------------------------------------------------


class TraceModel(Base):
    """Top-level trace representing an agentic workflow execution."""

    __tablename__ = "traces"

    trace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(512), nullable=False)
    status: Mapped[str] = mapped_column(
        SAEnum(TraceStatus, name="trace_status", create_constraint=False, native_enum=False, length=20),
        default=TraceStatus.PENDING,
        nullable=False,
    )
    input: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    output: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, default=dict, nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)

    spans: Mapped[list["SpanModel"]] = relationship(back_populates="trace", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_traces_org_id_created", "org_id", "created_at"),
    )


class SpanModel(Base):
    """A single unit of work within a trace."""

    __tablename__ = "spans"

    span_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    trace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("traces.trace_id"), nullable=False)
    parent_span_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    name: Mapped[str] = mapped_column(String(512), nullable=False)
    kind: Mapped[str] = mapped_column(
        SAEnum(SpanKind, name="span_kind", create_constraint=False, native_enum=False, length=20),
        default=SpanKind.OTHER,
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        SAEnum(SpanStatusCode, name="span_status_code", create_constraint=False, native_enum=False, length=20),
        default=SpanStatusCode.UNSET,
        nullable=False,
    )
    input: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    output: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    model: Mapped[str | None] = mapped_column(String(255), nullable=True)
    token_usage: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, default=dict, nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    trace: Mapped["TraceModel"] = relationship(back_populates="spans")

    __table_args__ = (
        Index("ix_spans_trace_id", "trace_id"),
    )
