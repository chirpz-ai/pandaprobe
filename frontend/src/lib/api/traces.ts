import { client } from "./client";
import type {
  TraceCreate,
  TraceUpdate,
  TraceAccepted,
  TraceResponse,
  TraceListItem,
  SpanCreate,
  SpanUpdate,
  SpanResponse,
  SpansAccepted,
  BatchDeleteRequest,
  BatchDeleteResponse,
  BatchTagsRequest,
  BatchTagsResponse,
  AnalyticsBucket,
  TokenCostBucket,
  TopModel,
  UserSummary,
  PaginatedResponse,
} from "./types";
import type {
  TraceSortBy,
  SortOrder,
  TraceStatus,
  AnalyticsMetric,
  AnalyticsGranularity,
} from "./enums";

export async function createTrace(
  data: TraceCreate
): Promise<TraceAccepted> {
  const res = await client.post<TraceAccepted>("/traces", data);
  return res.data;
}

export interface ListTracesParams {
  limit?: number;
  offset?: number;
  session_id?: string;
  status?: TraceStatus;
  user_id?: string;
  tags?: string[];
  name?: string;
  started_after?: string;
  started_before?: string;
  sort_by?: TraceSortBy;
  sort_order?: SortOrder;
}

export async function listTraces(
  params?: ListTracesParams
): Promise<PaginatedResponse<TraceListItem>> {
  const res = await client.get<PaginatedResponse<TraceListItem>>("/traces", {
    params,
  });
  return res.data;
}

export interface TraceAnalyticsParams {
  metric: AnalyticsMetric;
  granularity?: AnalyticsGranularity;
  started_after: string;
  started_before: string;
}

export async function getTraceAnalytics(
  params: TraceAnalyticsParams
): Promise<AnalyticsBucket[] | TokenCostBucket[] | TopModel[]> {
  const res = await client.get<
    AnalyticsBucket[] | TokenCostBucket[] | TopModel[]
  >("/traces/analytics", { params });
  return res.data;
}

export async function listTraceUsers(params?: {
  limit?: number;
  offset?: number;
}): Promise<PaginatedResponse<UserSummary>> {
  const res = await client.get<PaginatedResponse<UserSummary>>(
    "/traces/users",
    { params }
  );
  return res.data;
}

export async function batchDeleteTraces(
  data: BatchDeleteRequest
): Promise<BatchDeleteResponse> {
  const res = await client.post<BatchDeleteResponse>(
    "/traces/batch/delete",
    data
  );
  return res.data;
}

export async function batchUpdateTags(
  data: BatchTagsRequest
): Promise<BatchTagsResponse> {
  const res = await client.post<BatchTagsResponse>(
    "/traces/batch/tags",
    data
  );
  return res.data;
}

export async function getTrace(traceId: string): Promise<TraceResponse> {
  const res = await client.get<TraceResponse>(`/traces/${traceId}`);
  return res.data;
}

export async function updateTrace(
  traceId: string,
  data: TraceUpdate
): Promise<TraceResponse> {
  const res = await client.patch<TraceResponse>(`/traces/${traceId}`, data);
  return res.data;
}

export async function deleteTrace(traceId: string): Promise<void> {
  await client.delete(`/traces/${traceId}`);
}

export async function createSpans(
  traceId: string,
  data: SpanCreate[]
): Promise<SpansAccepted> {
  const res = await client.post<SpansAccepted>(
    `/traces/${traceId}/spans`,
    data
  );
  return res.data;
}

export async function updateSpan(
  traceId: string,
  spanId: string,
  data: SpanUpdate
): Promise<SpanResponse> {
  const res = await client.patch<SpanResponse>(
    `/traces/${traceId}/spans/${spanId}`,
    data
  );
  return res.data;
}
