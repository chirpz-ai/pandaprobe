"""SQLAlchemy ORM models for PandaProbe.

All table definitions live here so that Alembic can discover them via
``Base.metadata`` for auto-generated migrations.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum as SAEnum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from app.registry.constants import (
    EvaluationStatus,
    InvitationStatus,
    MembershipRole,
    MonitorStatus,
    ScoreDataType,
    ScoreSource,
    ScoreStatus,
    SpanKind,
    SpanStatusCode,
    SubscriptionPlan,
    SubscriptionStatus,
    TraceStatus,
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    """Shared declarative base for every ORM model."""

    pass


# ---------------------------------------------------------------------------
# Users & Identity
# ---------------------------------------------------------------------------


class UserModel(Base):
    """Registered user linked to an external identity provider."""

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    external_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    last_sign_in_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    memberships: Mapped[list["MembershipModel"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    sent_invitations: Mapped[list["InvitationModel"]] = relationship(back_populates="inviter", cascade="all, delete-orphan")


class OrganizationModel(Base):
    """Tenant account."""

    __tablename__ = "organizations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)

    memberships: Mapped[list["MembershipModel"]] = relationship(
        back_populates="organization", cascade="all, delete-orphan"
    )
    projects: Mapped[list["ProjectModel"]] = relationship(back_populates="organization", cascade="all, delete-orphan")
    api_keys: Mapped[list["APIKeyModel"]] = relationship(back_populates="organization", cascade="all, delete-orphan")
    subscription: Mapped["SubscriptionModel | None"] = relationship(
        back_populates="organization", uselist=False, cascade="all, delete-orphan"
    )
    usage_records: Mapped[list["UsageRecordModel"]] = relationship(
        back_populates="organization", cascade="all, delete-orphan"
    )
    invitations: Mapped[list["InvitationModel"]] = relationship(
        back_populates="organization", cascade="all, delete-orphan"
    )


class MembershipModel(Base):
    """Join table linking users to organizations with a role."""

    __tablename__ = "memberships"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    role: Mapped[str] = mapped_column(
        SAEnum(MembershipRole, name="membership_role", create_constraint=False, native_enum=False, length=20),
        default=MembershipRole.MEMBER,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)

    user: Mapped["UserModel"] = relationship(back_populates="memberships")
    organization: Mapped["OrganizationModel"] = relationship(back_populates="memberships")

    __table_args__ = (UniqueConstraint("user_id", "org_id", name="uq_membership_user_org"),)


class InvitationModel(Base):
    """Email-based invitation to join an organization."""

    __tablename__ = "invitations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    role: Mapped[str] = mapped_column(
        SAEnum(MembershipRole, name="membership_role", create_constraint=False, native_enum=False, length=20),
        default=MembershipRole.MEMBER,
        nullable=False,
    )
    invited_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    status: Mapped[str] = mapped_column(
        SAEnum(InvitationStatus, name="invitation_status", create_constraint=False, native_enum=False, length=20),
        default=InvitationStatus.PENDING,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    organization: Mapped["OrganizationModel"] = relationship(back_populates="invitations")
    inviter: Mapped["UserModel"] = relationship(back_populates="sent_invitations")

    __table_args__ = (
        Index("ix_invitation_org_email", "org_id", "email"),
    )


class ProjectModel(Base):
    """Project within an organization that groups traces."""

    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)

    organization: Mapped["OrganizationModel"] = relationship(back_populates="projects")
    traces: Mapped[list["TraceModel"]] = relationship(back_populates="project", passive_deletes=True)
    eval_runs: Mapped[list["EvalRunModel"]] = relationship(back_populates="project", passive_deletes=True)

    __table_args__ = (
        UniqueConstraint("org_id", "name", name="uq_project_org_name"),
        Index("ix_projects_org_id", "org_id"),
    )


class APIKeyModel(Base):
    """Hashed API key scoped to an organization."""

    __tablename__ = "api_keys"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    key_hash: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    key_prefix: Mapped[str] = mapped_column(String(12), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

    organization: Mapped["OrganizationModel"] = relationship(back_populates="api_keys")


# ---------------------------------------------------------------------------
# Traces
# ---------------------------------------------------------------------------


class TraceModel(Base):
    """Top-level trace representing an agentic workflow execution."""

    __tablename__ = "traces"

    trace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
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
    session_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    user_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    tags: Mapped[list[str]] = mapped_column(ARRAY(String), default=list, nullable=False)
    environment: Mapped[str | None] = mapped_column(String(255), nullable=True)
    release: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)

    project: Mapped["ProjectModel"] = relationship(back_populates="traces")
    spans: Mapped[list["SpanModel"]] = relationship(
        back_populates="trace",
        cascade="all, delete-orphan",
        order_by="SpanModel.started_at.asc(), SpanModel.span_id.asc()",
    )
    trace_scores: Mapped[list["TraceScoreModel"]] = relationship(back_populates="trace", passive_deletes=True)

    __table_args__ = (
        Index("ix_traces_project_id_created", "project_id", "created_at"),
        Index("ix_traces_session_id", "project_id", "session_id"),
        Index("ix_traces_tags", "tags", postgresql_using="gin"),
        Index("ix_traces_project_status", "project_id", "status"),
        Index("ix_traces_project_user_id", "project_id", "user_id"),
        Index("ix_traces_project_started", "project_id", "started_at"),
    )


class SpanModel(Base):
    """A single unit of work within a trace."""

    __tablename__ = "spans"

    span_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    trace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("traces.trace_id", ondelete="CASCADE"),
        nullable=False,
    )
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
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    completion_start_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    model_parameters: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    cost: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    trace: Mapped["TraceModel"] = relationship(back_populates="spans")

    __table_args__ = (Index("ix_spans_trace_id", "trace_id"),)


# ---------------------------------------------------------------------------
# Eval Monitors, Eval Runs & Trace Scores
# ---------------------------------------------------------------------------


class EvalMonitorModel(Base):
    """A persistent evaluation schedule that spawns eval runs on a cadence."""

    __tablename__ = "eval_monitors"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    target_type: Mapped[str] = mapped_column(String(20), nullable=False)
    metric_names: Mapped[list[str]] = mapped_column(ARRAY(String(255)), nullable=False)
    filters: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    sampling_rate: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    model: Mapped[str | None] = mapped_column(String(255), nullable=True)
    cadence: Mapped[str] = mapped_column(String(50), nullable=False)
    only_if_changed: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    status: Mapped[str] = mapped_column(
        SAEnum(MonitorStatus, name="monitor_status", create_constraint=False, native_enum=False, length=20),
        default=MonitorStatus.ACTIVE,
        nullable=False,
    )
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("eval_runs.id", ondelete="SET NULL", use_alter=True, name="fk_eval_monitors_last_run_id"),
        nullable=True,
    )
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )

    project: Mapped["ProjectModel"] = relationship()
    eval_runs: Mapped[list["EvalRunModel"]] = relationship(
        back_populates="monitor",
        foreign_keys="EvalRunModel.monitor_id",
        passive_deletes=True,
    )

    __table_args__ = (
        Index("ix_eval_monitors_project", "project_id", "status"),
        Index("ix_eval_monitors_next_run", "status", "next_run_at"),
    )


class EvalRunModel(Base):
    """A batch evaluation job that applies metrics to a filtered set of traces."""

    __tablename__ = "eval_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    target_type: Mapped[str] = mapped_column(String(20), default="TRACE", nullable=False)
    metric_names: Mapped[list[str]] = mapped_column(ARRAY(String(255)), nullable=False)
    filters: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    sampling_rate: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    model: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(
        SAEnum(EvaluationStatus, name="evaluation_status", create_constraint=False, native_enum=False, length=20),
        default=EvaluationStatus.PENDING,
        nullable=False,
    )
    total_targets: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    evaluated_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failed_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    monitor_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("eval_monitors.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    project: Mapped["ProjectModel"] = relationship(back_populates="eval_runs")
    trace_scores: Mapped[list["TraceScoreModel"]] = relationship(back_populates="eval_run", passive_deletes=True)
    monitor: Mapped["EvalMonitorModel | None"] = relationship(back_populates="eval_runs", foreign_keys=[monitor_id])

    __table_args__ = (Index("ix_eval_runs_project", "project_id", "created_at"),)


class TraceScoreModel(Base):
    """A single score for a single trace, from any source."""

    __tablename__ = "trace_scores"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    trace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("traces.trace_id", ondelete="CASCADE"),
        nullable=False,
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    data_type: Mapped[str] = mapped_column(
        SAEnum(ScoreDataType, name="score_data_type", create_constraint=False, native_enum=False, length=20),
        default=ScoreDataType.NUMERIC,
        nullable=False,
    )
    value: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source: Mapped[str] = mapped_column(
        SAEnum(ScoreSource, name="score_source", create_constraint=False, native_enum=False, length=20),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        SAEnum(ScoreStatus, name="score_status", create_constraint=False, native_enum=False, length=20),
        default=ScoreStatus.SUCCESS,
        nullable=False,
    )
    eval_run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("eval_runs.id", ondelete="SET NULL"),
        nullable=True,
    )
    author_user_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    environment: Mapped[str | None] = mapped_column(String(255), nullable=True)
    config_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )

    trace: Mapped["TraceModel"] = relationship(back_populates="trace_scores")
    project: Mapped["ProjectModel"] = relationship()
    eval_run: Mapped["EvalRunModel | None"] = relationship(back_populates="trace_scores")

    __table_args__ = (
        Index("ix_trace_scores_trace_id", "trace_id"),
        Index("ix_trace_scores_project_name", "project_id", "name"),
        Index("ix_trace_scores_eval_run", "eval_run_id"),
        Index("ix_trace_scores_project_created", "project_id", "created_at"),
    )


class SessionScoreModel(Base):
    """A single score for a session (agent-level), from any source."""

    __tablename__ = "session_scores"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[str] = mapped_column(String(255), nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    data_type: Mapped[str] = mapped_column(
        SAEnum(ScoreDataType, name="score_data_type", create_constraint=False, native_enum=False, length=20),
        default=ScoreDataType.NUMERIC,
        nullable=False,
    )
    value: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source: Mapped[str] = mapped_column(
        SAEnum(ScoreSource, name="score_source", create_constraint=False, native_enum=False, length=20),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        SAEnum(ScoreStatus, name="score_status", create_constraint=False, native_enum=False, length=20),
        default=ScoreStatus.SUCCESS,
        nullable=False,
    )
    eval_run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("eval_runs.id", ondelete="SET NULL"),
        nullable=True,
    )
    author_user_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    environment: Mapped[str | None] = mapped_column(String(255), nullable=True)
    config_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )

    project: Mapped["ProjectModel"] = relationship()
    eval_run: Mapped["EvalRunModel | None"] = relationship()

    __table_args__ = (
        Index("ix_session_scores_project_session", "project_id", "session_id"),
        Index("ix_session_scores_project_name", "project_id", "name", "created_at"),
        Index("ix_session_scores_eval_run", "eval_run_id"),
    )


# ---------------------------------------------------------------------------
# Subscriptions & Usage
# ---------------------------------------------------------------------------


class SubscriptionModel(Base):
    """An organization's subscription to a PandaProbe plan."""

    __tablename__ = "subscriptions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    plan: Mapped[str] = mapped_column(
        SAEnum(SubscriptionPlan, name="subscription_plan", create_constraint=False, native_enum=False, length=20),
        default=SubscriptionPlan.HOBBY,
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        SAEnum(SubscriptionStatus, name="subscription_status", create_constraint=False, native_enum=False, length=20),
        default=SubscriptionStatus.ACTIVE,
        nullable=False,
    )
    stripe_customer_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    stripe_subscription_id: Mapped[str | None] = mapped_column(String(255), nullable=True, unique=True)
    current_period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    current_period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    canceled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )

    organization: Mapped["OrganizationModel"] = relationship(back_populates="subscription")

    __table_args__ = (Index("ix_subscriptions_org_id", "org_id"),)


class UsageRecordModel(Base):
    """Aggregated usage counters for a single billing period."""

    __tablename__ = "usage_records"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    trace_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    trace_eval_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    session_eval_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    reported_trace_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    reported_trace_eval_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    reported_session_eval_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    billed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    stripe_invoice_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )

    organization: Mapped["OrganizationModel"] = relationship(back_populates="usage_records")

    __table_args__ = (
        UniqueConstraint("org_id", "period_start", name="uq_usage_record_org_period"),
        Index("ix_usage_records_org_period", "org_id", "period_start"),
    )
