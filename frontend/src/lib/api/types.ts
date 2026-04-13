import type {
  SpanKind,
  SpanStatusCode,
  TraceStatus,
  EvaluationStatus,
  ScoreSource,
  ScoreStatus,
  ScoreDataType,
  MembershipRole,
  SubscriptionPlan,
  SubscriptionStatus,
  MonitorStatus,
  KeyExpiration,
} from "./enums";

/* ─── Generic ──────────────────────────────────────────────────────────────── */

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}

/* ─── User ─────────────────────────────────────────────────────────────────── */

export interface UserProfileResponse {
  id: string;
  email: string;
  display_name: string;
  created_at: string;
  last_sign_in_at: string | null;
}

/* ─── Organizations ────────────────────────────────────────────────────────── */

export interface CreateOrganizationRequest {
  name: string;
}

export interface UpdateOrganizationRequest {
  name?: string;
}

export interface OrganizationResponse {
  id: string;
  name: string;
  created_at: string;
}

export interface MyOrganizationResponse extends OrganizationResponse {
  role: MembershipRole;
}

export interface MembershipResponse {
  id: string;
  user_id: string;
  org_id: string;
  role: MembershipRole;
  display_name: string;
  email: string;
  created_at: string;
}

export interface AddMemberRequest {
  user_id: string;
  role?: MembershipRole;
}

export interface UpdateMemberRoleRequest {
  role: MembershipRole;
}

/* ─── Projects ─────────────────────────────────────────────────────────────── */

export interface CreateProjectRequest {
  name: string;
  description?: string;
}

export interface UpdateProjectRequest {
  name?: string;
  description?: string;
}

export interface ProjectResponse {
  id: string;
  org_id: string;
  name: string;
  description: string;
  created_at: string;
}

/* ─── API Keys ─────────────────────────────────────────────────────────────── */

export interface CreateAPIKeyRequest {
  name: string;
  expiration?: KeyExpiration;
}

export interface APIKeyResponse {
  id: string;
  org_id: string;
  key_prefix: string;
  name: string;
  is_active: boolean;
  created_at: string;
  expires_at: string | null;
  raw_key: string | null;
}

/* ─── Subscriptions ────────────────────────────────────────────────────────── */

export interface SubscriptionResponse {
  id: string;
  org_id: string;
  plan: SubscriptionPlan;
  status: SubscriptionStatus;
  current_period_start: string;
  current_period_end: string;
  canceled_at: string | null;
  created_at: string;
}

export interface UsageResponse {
  plan: SubscriptionPlan;
  status: SubscriptionStatus;
  period_start: string;
  period_end: string;
  traces: number;
  trace_evals: number;
  session_evals: number;
  limits: Record<string, unknown>;
}

export interface CategoryBreakdown {
  used: number;
  included: number | null;
  overage_units: number;
  overage_cost: string;
}

export interface BillingResponse {
  plan: SubscriptionPlan;
  period_start: string;
  period_end: string;
  base_price_cents: number;
  overage_unit_price: string;
  traces: CategoryBreakdown;
  trace_evals: CategoryBreakdown;
  session_evals: CategoryBreakdown;
  total_overage_cost: string;
  reported_overage_cost: string;
  pending_overage_cost: string;
  estimated_total_cents: number;
}

export interface UsageHistoryItem {
  period_start: string;
  period_end: string;
  trace_count: number;
  trace_eval_count: number;
  session_eval_count: number;
  billed: boolean;
  stripe_invoice_id: string | null;
}

export interface PlanInfo {
  name: string;
  base_traces: number | null;
  base_trace_evals: number | null;
  base_session_evals: number | null;
  monitoring_allowed: boolean;
  max_members: number | null;
  pay_as_you_go: boolean;
  monthly_price_cents: number;
  overage_unit_price: string;
}

export interface CheckoutRequest {
  plan: SubscriptionPlan;
  success_url: string;
  cancel_url: string;
}

export interface CheckoutResponse {
  checkout_url: string;
}

export interface PortalRequest {
  return_url: string;
}

export interface PortalResponse {
  portal_url: string;
}

/* ─── Traces ───────────────────────────────────────────────────────────────── */

export interface SpanCreate {
  span_id?: string;
  parent_span_id?: string | null;
  name: string;
  kind?: SpanKind;
  status?: SpanStatusCode;
  input?: unknown;
  output?: unknown;
  model?: string | null;
  token_usage?: Record<string, unknown> | null;
  metadata?: Record<string, unknown>;
  started_at: string;
  ended_at?: string | null;
  error?: string | null;
  completion_start_time?: string | null;
  model_parameters?: Record<string, unknown> | null;
  cost?: Record<string, number> | null;
}

export interface SpanUpdate {
  name?: string;
  kind?: SpanKind;
  status?: SpanStatusCode;
  input?: unknown;
  output?: unknown;
  model?: string | null;
  token_usage?: Record<string, unknown> | null;
  metadata?: Record<string, unknown>;
  ended_at?: string | null;
  error?: string | null;
  completion_start_time?: string | null;
  model_parameters?: Record<string, unknown> | null;
  cost?: Record<string, number> | null;
}

export interface SpanResponse {
  span_id: string;
  trace_id: string;
  parent_span_id: string | null;
  name: string;
  kind: SpanKind;
  status: SpanStatusCode;
  input: unknown;
  output: unknown;
  model: string | null;
  token_usage: Record<string, unknown> | null;
  metadata: Record<string, unknown>;
  started_at: string | null;
  ended_at: string | null;
  completion_start_time: string | null;
  error: string | null;
  model_parameters: Record<string, unknown> | null;
  cost: Record<string, number> | null;
  latency_ms: number | null;
  time_to_first_token_ms: number | null;
}

export interface TraceCreate {
  trace_id?: string;
  name: string;
  status?: TraceStatus;
  input?: unknown;
  output?: unknown;
  metadata?: Record<string, unknown>;
  started_at: string;
  ended_at?: string | null;
  session_id?: string | null;
  user_id?: string | null;
  environment?: string | null;
  release?: string | null;
  tags?: string[];
  spans?: SpanCreate[];
}

export interface TraceUpdate {
  name?: string;
  status?: TraceStatus;
  input?: unknown;
  output?: unknown;
  metadata?: Record<string, unknown>;
  ended_at?: string | null;
  session_id?: string | null;
  user_id?: string | null;
  tags?: string[];
  environment?: string | null;
  release?: string | null;
}

export interface TraceAccepted {
  trace_id: string;
  task_id: string;
}

export interface TraceResponse {
  trace_id: string;
  project_id: string;
  name: string;
  status: TraceStatus;
  input: unknown;
  output: unknown;
  metadata: Record<string, unknown>;
  started_at: string | null;
  ended_at: string | null;
  session_id: string | null;
  user_id: string | null;
  tags: string[];
  environment: string | null;
  release: string | null;
  spans: SpanResponse[];
  total_tokens: number;
  total_cost: number;
}

export interface TraceListItem {
  trace_id: string;
  name: string;
  status: TraceStatus;
  started_at: string | null;
  ended_at: string | null;
  session_id: string | null;
  user_id: string | null;
  tags: string[];
  environment: string | null;
  release: string | null;
  latency_ms: number | null;
  span_count: number;
  total_tokens: number;
  total_cost: number;
}

export interface SpansAccepted {
  span_ids: string[];
}

export interface BatchDeleteRequest {
  trace_ids: string[];
}

export interface BatchDeleteResponse {
  deleted: number;
}

export interface BatchTagsRequest {
  trace_ids: string[];
  add_tags?: string[];
  remove_tags?: string[];
}

export interface BatchTagsResponse {
  updated: number;
}

export interface AnalyticsBucket {
  bucket: string;
  trace_count: number;
  error_count: number;
  avg_latency_ms: number | null;
  p50_latency_ms: number | null;
  p90_latency_ms: number | null;
  p99_latency_ms: number | null;
}

export interface TokenCostBucket {
  bucket: string;
  total_tokens: number;
  prompt_tokens: number;
  completion_tokens: number;
  total_cost: number;
}

export interface TopModel {
  model: string;
  call_count: number;
  total_tokens: number;
  total_cost: number;
}

export interface UserSummary {
  user_id: string;
  trace_count: number;
  first_seen: string;
  last_seen: string;
  error_count: number;
}

/* ─── Sessions ─────────────────────────────────────────────────────────────── */

export interface SessionSummary {
  session_id: string;
  trace_count: number;
  first_trace_at: string | null;
  last_trace_at: string | null;
  total_latency_ms: number | null;
  has_error: boolean;
  user_id: string | null;
  tags: string[];
  total_span_count: number;
  total_tokens: number;
  total_cost: number;
}

export interface SessionDetail extends SessionSummary {
  traces: TraceResponse[];
}

export interface SessionDeleteResponse {
  deleted: number;
}

export interface SessionAnalyticsBucket {
  bucket: string;
  session_count: number;
  avg_traces_per_session: number | null;
  avg_session_duration_ms: number | null;
}

/* ─── Evaluations ──────────────────────────────────────────────────────────── */

export interface PromptPreview {
  stage: string;
  prompt: string;
}

export interface MetricSummary {
  name: string;
  description: string;
  category: string;
}

export interface MetricInfo extends MetricSummary {
  default_threshold: number;
  prompt_preview: PromptPreview[];
}

export interface ProviderInfo {
  key: string;
  name: string;
  description: string;
  available: boolean;
  message: string;
}

export interface EvalRunFilters {
  date_from?: string | null;
  date_to?: string | null;
  session_id?: string | null;
  user_id?: string | null;
  name?: string | null;
  status?: TraceStatus | null;
  tags?: string[] | null;
}

export interface CreateEvalRunRequest {
  name?: string | null;
  metrics: string[];
  filters?: EvalRunFilters;
  sampling_rate?: number;
  model?: string | null;
}

export interface CreateBatchEvalRunRequest {
  trace_ids: string[];
  metrics: string[];
  name?: string | null;
  model?: string | null;
}

export interface EvalRunResponse {
  id: string;
  project_id: string;
  name: string | null;
  status: EvaluationStatus;
  metric_names: string[];
  total_targets: number;
  evaluated_count: number;
  failed_count: number;
  created_at: string | null;
  completed_at: string | null;
  target_type: string;
  filters: Record<string, unknown>;
  sampling_rate: number;
  model: string | null;
  monitor_id: string | null;
  error_message: string | null;
}

export interface EvalRunTemplate {
  metric: MetricInfo;
  filters: EvalRunFilters;
  sampling_rate: number;
  model: string | null;
}

/* ─── Trace Scores ─────────────────────────────────────────────────────────── */

export interface TraceScoreResponse {
  id: string;
  trace_id: string;
  project_id: string;
  name: string;
  value: string | null;
  status: ScoreStatus;
  source: ScoreSource;
  created_at: string;
  updated_at: string;
  data_type: ScoreDataType;
  eval_run_id: string | null;
  author_user_id: string | null;
  reason: string | null;
  environment: string | null;
  config_id: string | null;
  metadata: Record<string, unknown>;
}

export interface CreateTraceScoreRequest {
  trace_id: string;
  name: string;
  value: string;
  data_type?: ScoreDataType;
  source?: ScoreSource;
  reason?: string | null;
  metadata?: Record<string, unknown>;
}

export interface UpdateTraceScoreRequest {
  value?: string | null;
  reason?: string | null;
  metadata?: Record<string, unknown> | null;
}

/* ─── Score Analytics ──────────────────────────────────────────────────────── */

export interface ScoreSummaryItem {
  metric_name: string;
  avg_score: number | null;
  min_score: number | null;
  max_score: number | null;
  median_score: number | null;
  success_count: number;
  failed_count: number;
  latest_score_at: string | null;
}

export interface ScoreTrendItem {
  bucket: string | null;
  metric_name: string;
  avg_score: number;
  count: number;
}

export interface ScoreDistributionItem {
  bucket: number;
  bucket_min: number;
  bucket_max: number;
  count: number;
}

/* ─── Session Eval Runs ────────────────────────────────────────────────────── */

export interface SessionEvalRunFilters {
  date_from?: string | null;
  date_to?: string | null;
  user_id?: string | null;
  has_error?: boolean | null;
  tags?: string[] | null;
  min_trace_count?: number | null;
}

export interface CreateSessionEvalRunRequest {
  name?: string | null;
  metrics: string[];
  filters?: SessionEvalRunFilters;
  sampling_rate?: number;
  model?: string | null;
  signal_weights?: Record<string, number> | null;
}

export interface CreateBatchSessionEvalRunRequest {
  session_ids: string[];
  metrics: string[];
  name?: string | null;
  model?: string | null;
  signal_weights?: Record<string, number> | null;
}

/* ─── Session Scores ───────────────────────────────────────────────────────── */

export interface SessionScoreResponse {
  id: string;
  session_id: string;
  project_id: string;
  name: string;
  data_type: string;
  value: string;
  source: string;
  status: string;
  eval_run_id: string | null;
  author_user_id: string | null;
  reason: string | null;
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface SessionScoreHistoryItem {
  metric_name: string;
  score: number | null;
  eval_run_id: string | null;
  created_at: string | null;
  status: string;
}

export interface SessionComparisonItem {
  session_id: string;
  score: number | null;
  evaluated_at: string | null;
  eval_run_id: string | null;
}

/* ─── Monitors ─────────────────────────────────────────────────────────────── */

export interface CreateMonitorRequest {
  name: string;
  target_type: string;
  metrics: string[];
  filters?: Record<string, unknown>;
  sampling_rate?: number;
  model?: string | null;
  cadence: string;
  only_if_changed?: boolean;
  signal_weights?: Record<string, number> | null;
}

export interface UpdateMonitorRequest {
  name?: string;
  metrics?: string[];
  filters?: Record<string, unknown>;
  sampling_rate?: number | null;
  model?: string | null;
  cadence?: string;
  only_if_changed?: boolean;
  signal_weights?: Record<string, number> | null;
}

export interface MonitorResponse {
  id: string;
  project_id: string;
  name: string;
  target_type: string;
  metric_names: string[];
  filters: Record<string, unknown>;
  sampling_rate: number;
  model: string | null;
  cadence: string;
  status: MonitorStatus;
  only_if_changed: boolean;
  last_run_at: string | null;
  last_run_id: string | null;
  next_run_at: string | null;
  created_at: string;
  updated_at: string;
}
