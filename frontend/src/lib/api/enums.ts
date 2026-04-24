export const SpanKind = {
  AGENT: "AGENT",
  TOOL: "TOOL",
  LLM: "LLM",
  RETRIEVER: "RETRIEVER",
  CHAIN: "CHAIN",
  EMBEDDING: "EMBEDDING",
  OTHER: "OTHER",
} as const;
export type SpanKind = (typeof SpanKind)[keyof typeof SpanKind];

export const SpanStatusCode = {
  UNSET: "UNSET",
  OK: "OK",
  ERROR: "ERROR",
} as const;
export type SpanStatusCode =
  (typeof SpanStatusCode)[keyof typeof SpanStatusCode];

export const TraceStatus = {
  PENDING: "PENDING",
  RUNNING: "RUNNING",
  COMPLETED: "COMPLETED",
  ERROR: "ERROR",
} as const;
export type TraceStatus = (typeof TraceStatus)[keyof typeof TraceStatus];

export const EvaluationStatus = {
  PENDING: "PENDING",
  RUNNING: "RUNNING",
  COMPLETED: "COMPLETED",
  FAILED: "FAILED",
} as const;
export type EvaluationStatus =
  (typeof EvaluationStatus)[keyof typeof EvaluationStatus];

export const ScoreSource = {
  AUTOMATED: "AUTOMATED",
  ANNOTATION: "ANNOTATION",
  PROGRAMMATIC: "PROGRAMMATIC",
} as const;
export type ScoreSource = (typeof ScoreSource)[keyof typeof ScoreSource];

export const ScoreStatus = {
  SUCCESS: "SUCCESS",
  FAILED: "FAILED",
  PENDING: "PENDING",
} as const;
export type ScoreStatus = (typeof ScoreStatus)[keyof typeof ScoreStatus];

export const ScoreDataType = {
  NUMERIC: "NUMERIC",
  BOOLEAN: "BOOLEAN",
  CATEGORICAL: "CATEGORICAL",
} as const;
export type ScoreDataType = (typeof ScoreDataType)[keyof typeof ScoreDataType];

export const MembershipRole = {
  OWNER: "OWNER",
  ADMIN: "ADMIN",
  MEMBER: "MEMBER",
} as const;
export type MembershipRole =
  (typeof MembershipRole)[keyof typeof MembershipRole];

export const InvitationStatus = {
  PENDING: "PENDING",
  ACCEPTED: "ACCEPTED",
  DECLINED: "DECLINED",
  REVOKED: "REVOKED",
  EXPIRED: "EXPIRED",
} as const;
export type InvitationStatus =
  (typeof InvitationStatus)[keyof typeof InvitationStatus];

export const TraceSortBy = {
  started_at: "started_at",
  ended_at: "ended_at",
  name: "name",
  latency: "latency",
  status: "status",
} as const;
export type TraceSortBy = (typeof TraceSortBy)[keyof typeof TraceSortBy];

export const SortOrder = {
  asc: "asc",
  desc: "desc",
} as const;
export type SortOrder = (typeof SortOrder)[keyof typeof SortOrder];

export const AnalyticsMetric = {
  volume: "volume",
  errors: "errors",
  latency: "latency",
  cost: "cost",
  tokens: "tokens",
  models: "models",
} as const;
export type AnalyticsMetric =
  (typeof AnalyticsMetric)[keyof typeof AnalyticsMetric];

export const SessionSortBy = {
  recent: "recent",
  trace_count: "trace_count",
  latency: "latency",
  cost: "cost",
} as const;
export type SessionSortBy = (typeof SessionSortBy)[keyof typeof SessionSortBy];

export const AnalyticsGranularity = {
  hour: "hour",
  day: "day",
  week: "week",
} as const;
export type AnalyticsGranularity =
  (typeof AnalyticsGranularity)[keyof typeof AnalyticsGranularity];

export const MonitorStatus = {
  ACTIVE: "ACTIVE",
  PAUSED: "PAUSED",
} as const;
export type MonitorStatus = (typeof MonitorStatus)[keyof typeof MonitorStatus];

export const MonitorCadence = {
  every_6h: "every_6h",
  daily: "daily",
  weekly: "weekly",
  custom: "custom",
} as const;
export type MonitorCadence =
  (typeof MonitorCadence)[keyof typeof MonitorCadence];

export const SubscriptionPlan = {
  HOBBY: "HOBBY",
  PRO: "PRO",
  STARTUP: "STARTUP",
  ENTERPRISE: "ENTERPRISE",
  DEVELOPMENT: "DEVELOPMENT",
} as const;
export type SubscriptionPlan =
  (typeof SubscriptionPlan)[keyof typeof SubscriptionPlan];

export const SubscriptionStatus = {
  ACTIVE: "ACTIVE",
  PAST_DUE: "PAST_DUE",
  CANCELED: "CANCELED",
  INCOMPLETE: "INCOMPLETE",
} as const;
export type SubscriptionStatus =
  (typeof SubscriptionStatus)[keyof typeof SubscriptionStatus];

export const UsageCategory = {
  traces: "traces",
  trace_evals: "trace_evals",
  session_evals: "session_evals",
} as const;
export type UsageCategory = (typeof UsageCategory)[keyof typeof UsageCategory];

export const KeyExpiration = {
  never: "never",
  "90d": "90d",
} as const;
export type KeyExpiration = (typeof KeyExpiration)[keyof typeof KeyExpiration];
