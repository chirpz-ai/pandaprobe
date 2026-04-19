export const queryKeys = {
  organizations: {
    all: ["organizations"] as const,
    list: () => [...queryKeys.organizations.all, "list"] as const,
    detail: (orgId: string) => [...queryKeys.organizations.all, orgId] as const,
  },
  projects: {
    all: (orgId: string) => ["projects", orgId] as const,
    list: (orgId: string) =>
      [...queryKeys.projects.all(orgId), "list"] as const,
  },
  members: {
    list: (orgId: string) => ["members", orgId] as const,
  },
  apiKeys: {
    list: (orgId: string) => ["apiKeys", orgId] as const,
  },
  traces: {
    all: (projectId: string) => ["traces", projectId] as const,
    list: (projectId: string, params: Record<string, unknown>) =>
      [...queryKeys.traces.all(projectId), params] as const,
    detail: (traceId: string) => ["traces", "detail", traceId] as const,
  },
  sessions: {
    all: (projectId: string) => ["sessions", projectId] as const,
    list: (projectId: string, params: Record<string, unknown>) =>
      [...queryKeys.sessions.all(projectId), params] as const,
    detail: (sessionId: string) => ["sessions", "detail", sessionId] as const,
  },
  evaluations: {
    traceRuns: {
      all: (projectId: string) => ["traceRuns", projectId] as const,
      list: (projectId: string, params: Record<string, unknown>) =>
        ["traceRuns", projectId, params] as const,
    },
    sessionRuns: {
      all: (projectId: string) => ["sessionRuns", projectId] as const,
      list: (projectId: string, params: Record<string, unknown>) =>
        ["sessionRuns", projectId, params] as const,
    },
    monitors: {
      all: (projectId: string) => ["monitors", projectId] as const,
      list: (projectId: string, params: Record<string, unknown>) =>
        ["monitors", projectId, params] as const,
      detail: (monitorId: string) =>
        ["monitors", "detail", monitorId] as const,
      runs: (monitorId: string, params: Record<string, unknown>) =>
        ["monitors", "runs", monitorId, params] as const,
    },
    traceScores: {
      all: (projectId: string) => ["traceScores", projectId] as const,
      list: (projectId: string, params: Record<string, unknown>) =>
        ["traceScores", projectId, params] as const,
    },
    sessionScores: {
      all: (projectId: string) => ["sessionScores", projectId] as const,
      list: (projectId: string, params: Record<string, unknown>) =>
        ["sessionScores", projectId, params] as const,
    },
  },
  analytics: {
    traces: (projectId: string, params: Record<string, unknown>) =>
      ["analytics", "traces", projectId, params] as const,
    scores: (projectId: string, params: Record<string, unknown>) =>
      ["analytics", "scores", projectId, params] as const,
  },
  subscriptions: {
    current: (orgId: string) => ["subscription", orgId] as const,
    usage: (orgId: string) => ["subscription", orgId, "usage"] as const,
    billing: (orgId: string) => ["subscription", orgId, "billing"] as const,
    invoices: (orgId: string) => ["subscription", orgId, "invoices"] as const,
    plans: ["subscription", "plans"] as const,
  },
  dashboardStats: {
    home: (projectId: string | null) => ["dashboardStats", projectId] as const,
  },
};
