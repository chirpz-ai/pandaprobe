import { client } from "./client";
import type {
  ProviderInfo,
  MetricSummary,
  EvalRunTemplate,
  CreateEvalRunRequest,
  CreateBatchEvalRunRequest,
  EvalRunResponse,
  TraceScoreResponse,
  CreateTraceScoreRequest,
  UpdateTraceScoreRequest,
  ScoreSummaryItem,
  ScoreTrendItem,
  ScoreDistributionItem,
  CreateSessionEvalRunRequest,
  CreateBatchSessionEvalRunRequest,
  SessionScoreResponse,
  SessionScoreHistoryItem,
  SessionComparisonItem,
  CreateMonitorRequest,
  UpdateMonitorRequest,
  MonitorResponse,
  PaginatedResponse,
} from "./types";
import type { EvaluationStatus, MonitorStatus } from "./enums";

/* ─── Metric Discovery ─────────────────────────────────────────────────────── */

export async function getProviders(): Promise<ProviderInfo[]> {
  const res = await client.get<ProviderInfo[]>("/evaluations/providers");
  return res.data;
}

export async function getTraceMetrics(): Promise<MetricSummary[]> {
  const res = await client.get<MetricSummary[]>("/evaluations/trace-metrics");
  return res.data;
}

export async function getSessionMetrics(): Promise<MetricSummary[]> {
  const res = await client.get<MetricSummary[]>("/evaluations/session-metrics");
  return res.data;
}

/* ─── Trace Eval Runs ──────────────────────────────────────────────────────── */

export async function getTraceRunTemplate(
  metric: string,
): Promise<EvalRunTemplate> {
  const res = await client.get<EvalRunTemplate>(
    "/evaluations/trace-runs/template",
    { params: { metric } },
  );
  return res.data;
}

export async function createTraceRun(
  data: CreateEvalRunRequest,
): Promise<EvalRunResponse> {
  const res = await client.post<EvalRunResponse>(
    "/evaluations/trace-runs",
    data,
  );
  return res.data;
}

export async function createBatchTraceRun(
  data: CreateBatchEvalRunRequest,
): Promise<EvalRunResponse> {
  const res = await client.post<EvalRunResponse>(
    "/evaluations/trace-runs/batch",
    data,
  );
  return res.data;
}

export async function listTraceRuns(params?: {
  status?: EvaluationStatus;
  limit?: number;
  offset?: number;
}): Promise<PaginatedResponse<EvalRunResponse>> {
  const res = await client.get<PaginatedResponse<EvalRunResponse>>(
    "/evaluations/trace-runs",
    { params },
  );
  return res.data;
}

export async function getTraceRun(runId: string): Promise<EvalRunResponse> {
  const res = await client.get<EvalRunResponse>(
    `/evaluations/trace-runs/${runId}`,
  );
  return res.data;
}

export async function deleteTraceRun(
  runId: string,
  deleteScores = false,
): Promise<void> {
  await client.delete(`/evaluations/trace-runs/${runId}`, {
    params: { delete_scores: deleteScores },
  });
}

export async function retryTraceRun(runId: string): Promise<EvalRunResponse> {
  const res = await client.post<EvalRunResponse>(
    `/evaluations/trace-runs/${runId}/retry`,
  );
  return res.data;
}

export async function getTraceRunScores(
  runId: string,
): Promise<TraceScoreResponse[]> {
  const res = await client.get<TraceScoreResponse[]>(
    `/evaluations/trace-runs/${runId}/scores`,
  );
  return res.data;
}

/* ─── Trace Scores ─────────────────────────────────────────────────────────── */

export async function createTraceScore(
  data: CreateTraceScoreRequest,
): Promise<TraceScoreResponse> {
  const res = await client.post<TraceScoreResponse>(
    "/evaluations/trace-scores",
    data,
  );
  return res.data;
}

export interface ListTraceScoresParams {
  trace_id?: string;
  name?: string;
  source?: string;
  status?: string;
  data_type?: string;
  eval_run_id?: string;
  environment?: string;
  date_from?: string;
  date_to?: string;
  limit?: number;
  offset?: number;
}

export async function listTraceScores(
  params?: ListTraceScoresParams,
): Promise<PaginatedResponse<TraceScoreResponse>> {
  const res = await client.get<PaginatedResponse<TraceScoreResponse>>(
    "/evaluations/trace-scores",
    { params },
  );
  return res.data;
}

export async function getTraceScoresByTraceId(
  traceId: string,
): Promise<TraceScoreResponse[]> {
  const res = await client.get<TraceScoreResponse[]>(
    `/evaluations/trace-scores/${traceId}`,
  );
  return res.data;
}

export async function updateTraceScore(
  scoreId: string,
  data: UpdateTraceScoreRequest,
): Promise<TraceScoreResponse> {
  const res = await client.patch<TraceScoreResponse>(
    `/evaluations/trace-scores/${scoreId}`,
    data,
  );
  return res.data;
}

export async function deleteTraceScore(scoreId: string): Promise<void> {
  await client.delete(`/evaluations/trace-scores/${scoreId}`);
}

/* ─── Trace Score Analytics ────────────────────────────────────────────────── */

export async function getTraceScoreSummary(params?: {
  date_from?: string;
  date_to?: string;
}): Promise<ScoreSummaryItem[]> {
  const res = await client.get<ScoreSummaryItem[]>(
    "/evaluations/analytics/trace-scores/summary",
    { params },
  );
  return res.data;
}

export async function getTraceScoreTrend(params: {
  metric_name: string;
  date_from?: string;
  date_to?: string;
  granularity?: string;
}): Promise<ScoreTrendItem[]> {
  const res = await client.get<ScoreTrendItem[]>(
    "/evaluations/analytics/trace-scores/trend",
    { params },
  );
  return res.data;
}

export async function getTraceScoreDistribution(params: {
  metric_name: string;
  date_from?: string;
  date_to?: string;
  buckets?: number;
}): Promise<ScoreDistributionItem[]> {
  const res = await client.get<ScoreDistributionItem[]>(
    "/evaluations/analytics/trace-scores/distribution",
    { params },
  );
  return res.data;
}

/* ─── Session Eval Runs ────────────────────────────────────────────────────── */

export async function createSessionRun(
  data: CreateSessionEvalRunRequest,
): Promise<EvalRunResponse> {
  const res = await client.post<EvalRunResponse>(
    "/evaluations/session-runs",
    data,
  );
  return res.data;
}

export async function createBatchSessionRun(
  data: CreateBatchSessionEvalRunRequest,
): Promise<EvalRunResponse> {
  const res = await client.post<EvalRunResponse>(
    "/evaluations/session-runs/batch",
    data,
  );
  return res.data;
}

export async function listSessionRuns(params?: {
  status?: EvaluationStatus;
  limit?: number;
  offset?: number;
}): Promise<PaginatedResponse<EvalRunResponse>> {
  const res = await client.get<PaginatedResponse<EvalRunResponse>>(
    "/evaluations/session-runs",
    { params },
  );
  return res.data;
}

export async function getSessionRun(runId: string): Promise<EvalRunResponse> {
  const res = await client.get<EvalRunResponse>(
    `/evaluations/session-runs/${runId}`,
  );
  return res.data;
}

export async function deleteSessionRun(
  runId: string,
  deleteScores = false,
): Promise<void> {
  await client.delete(`/evaluations/session-runs/${runId}`, {
    params: { delete_scores: deleteScores },
  });
}

export async function retrySessionRun(runId: string): Promise<EvalRunResponse> {
  const res = await client.post<EvalRunResponse>(
    `/evaluations/session-runs/${runId}/retry`,
  );
  return res.data;
}

export async function getSessionRunScores(
  runId: string,
): Promise<SessionScoreResponse[]> {
  const res = await client.get<SessionScoreResponse[]>(
    `/evaluations/session-runs/${runId}/scores`,
  );
  return res.data;
}

/* ─── Session Scores ───────────────────────────────────────────────────────── */

export interface ListSessionScoresParams {
  session_id?: string;
  name?: string;
  source?: string;
  status?: string;
  eval_run_id?: string;
  date_from?: string;
  date_to?: string;
  limit?: number;
  offset?: number;
}

export async function listSessionScores(
  params?: ListSessionScoresParams,
): Promise<PaginatedResponse<SessionScoreResponse>> {
  const res = await client.get<PaginatedResponse<SessionScoreResponse>>(
    "/evaluations/session-scores",
    { params },
  );
  return res.data;
}

export async function getSessionScoresBySessionId(
  sessionId: string,
): Promise<SessionScoreResponse[]> {
  const res = await client.get<SessionScoreResponse[]>(
    `/evaluations/session-scores/${sessionId}`,
  );
  return res.data;
}

export async function deleteSessionScore(scoreId: string): Promise<void> {
  await client.delete(`/evaluations/session-scores/${scoreId}`);
}

/* ─── Session Score Analytics ──────────────────────────────────────────────── */

export async function getSessionScoreSummary(params?: {
  date_from?: string;
  date_to?: string;
}): Promise<ScoreSummaryItem[]> {
  const res = await client.get<ScoreSummaryItem[]>(
    "/evaluations/analytics/session-scores/summary",
    { params },
  );
  return res.data;
}

export async function getSessionScoreTrend(params: {
  metric_name: string;
  date_from?: string;
  date_to?: string;
  granularity?: string;
}): Promise<ScoreTrendItem[]> {
  const res = await client.get<ScoreTrendItem[]>(
    "/evaluations/analytics/session-scores/trend",
    { params },
  );
  return res.data;
}

export async function getSessionScoreDistribution(params: {
  metric_name: string;
  date_from?: string;
  date_to?: string;
  buckets?: number;
}): Promise<ScoreDistributionItem[]> {
  const res = await client.get<ScoreDistributionItem[]>(
    "/evaluations/analytics/session-scores/distribution",
    { params },
  );
  return res.data;
}

export async function getSessionScoreHistory(
  sessionId: string,
  params?: { metric_name?: string; limit?: number },
): Promise<SessionScoreHistoryItem[]> {
  const res = await client.get<SessionScoreHistoryItem[]>(
    `/evaluations/analytics/session-scores/history/${sessionId}`,
    { params },
  );
  return res.data;
}

export async function getSessionScoreComparison(params: {
  metric_name: string;
  sort_order?: string;
  limit?: number;
  offset?: number;
}): Promise<PaginatedResponse<SessionComparisonItem>> {
  const res = await client.get<PaginatedResponse<SessionComparisonItem>>(
    "/evaluations/analytics/session-scores/comparison",
    { params },
  );
  return res.data;
}

/* ─── Monitors ─────────────────────────────────────────────────────────────── */

export async function createMonitor(
  data: CreateMonitorRequest,
): Promise<MonitorResponse> {
  const res = await client.post<MonitorResponse>("/evaluations/monitors", data);
  return res.data;
}

export async function listMonitors(params?: {
  status?: MonitorStatus;
  limit?: number;
  offset?: number;
}): Promise<PaginatedResponse<MonitorResponse>> {
  const res = await client.get<PaginatedResponse<MonitorResponse>>(
    "/evaluations/monitors",
    { params },
  );
  return res.data;
}

export async function getMonitor(monitorId: string): Promise<MonitorResponse> {
  const res = await client.get<MonitorResponse>(
    `/evaluations/monitors/${monitorId}`,
  );
  return res.data;
}

export async function updateMonitor(
  monitorId: string,
  data: UpdateMonitorRequest,
): Promise<MonitorResponse> {
  const res = await client.patch<MonitorResponse>(
    `/evaluations/monitors/${monitorId}`,
    data,
  );
  return res.data;
}

export async function deleteMonitor(monitorId: string): Promise<void> {
  await client.delete(`/evaluations/monitors/${monitorId}`);
}

export async function pauseMonitor(
  monitorId: string,
): Promise<MonitorResponse> {
  const res = await client.post<MonitorResponse>(
    `/evaluations/monitors/${monitorId}/pause`,
  );
  return res.data;
}

export async function resumeMonitor(
  monitorId: string,
): Promise<MonitorResponse> {
  const res = await client.post<MonitorResponse>(
    `/evaluations/monitors/${monitorId}/resume`,
  );
  return res.data;
}

export async function triggerMonitor(
  monitorId: string,
): Promise<EvalRunResponse> {
  const res = await client.post<EvalRunResponse>(
    `/evaluations/monitors/${monitorId}/trigger`,
  );
  return res.data;
}

export async function getMonitorRuns(
  monitorId: string,
  params?: { limit?: number; offset?: number },
): Promise<PaginatedResponse<EvalRunResponse>> {
  const res = await client.get<PaginatedResponse<EvalRunResponse>>(
    `/evaluations/monitors/${monitorId}/runs`,
    { params },
  );
  return res.data;
}
