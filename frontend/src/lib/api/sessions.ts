import { client } from "./client";
import type {
  SessionSummary,
  SessionDetail,
  SessionDeleteResponse,
  SessionAnalyticsBucket,
  PaginatedResponse,
} from "./types";
import type { SessionSortBy, SortOrder, AnalyticsGranularity } from "./enums";

export interface ListSessionsParams {
  limit?: number;
  offset?: number;
  user_id?: string;
  has_error?: boolean;
  started_after?: string;
  started_before?: string;
  tags?: string[];
  query?: string;
  sort_by?: SessionSortBy;
  sort_order?: SortOrder;
}

export async function listSessions(
  params?: ListSessionsParams,
): Promise<PaginatedResponse<SessionSummary>> {
  const res = await client.get<PaginatedResponse<SessionSummary>>("/sessions", {
    params,
  });
  return res.data;
}

export interface SessionAnalyticsParams {
  granularity?: AnalyticsGranularity;
  started_after: string;
  started_before: string;
}

export async function getSessionAnalytics(
  params: SessionAnalyticsParams,
): Promise<SessionAnalyticsBucket[]> {
  const res = await client.get<SessionAnalyticsBucket[]>(
    "/sessions/analytics",
    { params },
  );
  return res.data;
}

export async function getSession(
  sessionId: string,
  params?: { limit?: number; offset?: number },
): Promise<SessionDetail> {
  const res = await client.get<SessionDetail>(`/sessions/${sessionId}`, {
    params,
  });
  return res.data;
}

export async function deleteSession(
  sessionId: string,
): Promise<SessionDeleteResponse> {
  const res = await client.delete<SessionDeleteResponse>(
    `/sessions/${sessionId}`,
  );
  return res.data;
}
