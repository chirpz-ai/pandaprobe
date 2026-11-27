import { http, HttpResponse } from "msw";
import { version } from "../../package.json";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export const handlers = [
  http.get(`${API}/health`, () =>
    HttpResponse.json({
      status: "healthy",
      version,
      environment: "development",
    }),
  ),

  http.get(`${API}/me`, () =>
    HttpResponse.json({
      id: "u-dev-001",
      email: "dev@pandaprobe.io",
      display_name: "Dev User",
      created_at: "2024-01-01T00:00:00Z",
      last_sign_in_at: null,
    }),
  ),

  http.get(`${API}/organizations`, () =>
    HttpResponse.json([
      {
        id: "org-001",
        name: "Dev Organization",
        created_at: "2024-01-01T00:00:00Z",
        role: "OWNER",
      },
    ]),
  ),

  http.get(`${API}/organizations/:orgId/projects`, () =>
    HttpResponse.json([
      {
        id: "proj-001",
        org_id: "org-001",
        name: "Default Project",
        description: "",
        created_at: "2024-01-01T00:00:00Z",
      },
    ]),
  ),

  http.get(`${API}/traces`, () =>
    HttpResponse.json({
      items: [
        {
          trace_id: "trace-001",
          name: "Sample Trace",
          status: "COMPLETED",
          started_at: "2024-06-01T10:00:00Z",
          ended_at: "2024-06-01T10:00:01Z",
          session_id: null,
          user_id: null,
          tags: ["test"],
          environment: null,
          release: null,
          latency_ms: 1000,
          span_count: 3,
          total_tokens: 500,
          total_cost: 0.005,
        },
      ],
      total: 1,
      limit: 50,
      offset: 0,
    }),
  ),

  http.get(`${API}/sessions`, () =>
    HttpResponse.json({
      items: [],
      total: 0,
      limit: 50,
      offset: 0,
    }),
  ),

  http.get(`${API}/organizations/:orgId/subscriptions`, () =>
    HttpResponse.json({
      id: "sub-001",
      org_id: "org-001",
      plan: "DEVELOPMENT",
      status: "ACTIVE",
      current_period_start: "2024-01-01T00:00:00Z",
      current_period_end: "2024-02-01T00:00:00Z",
      canceled_at: null,
      created_at: "2024-01-01T00:00:00Z",
    }),
  ),

  http.get(`${API}/organizations/:orgId/subscriptions/usage`, () =>
    HttpResponse.json({
      plan: "DEVELOPMENT",
      status: "ACTIVE",
      period_start: "2024-01-01T00:00:00Z",
      period_end: "2024-02-01T00:00:00Z",
      traces: 42,
      trace_evals: 10,
      session_evals: 5,
      total_events: 57,
      remaining_events: null,
      limits: {
        included_events: null,
        monitoring_allowed: true,
        max_members: 1,
        pay_as_you_go: false,
        monthly_price_cents: 0,
      },
    }),
  ),

  http.get(`${API}/evaluations/monitors`, () =>
    HttpResponse.json({ items: [], total: 0, limit: 50, offset: 0 }),
  ),
];
