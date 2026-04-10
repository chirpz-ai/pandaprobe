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
    traceRuns: (projectId: string) => ["traceRuns", projectId] as const,
    sessionRuns: (projectId: string) => ["sessionRuns", projectId] as const,
    monitors: (projectId: string) => ["monitors", projectId] as const,
  },
  analytics: {
    traces: (projectId: string, params: Record<string, unknown>) =>
      ["analytics", "traces", projectId, params] as const,
    scores: (projectId: string, params: Record<string, unknown>) =>
      ["analytics", "scores", projectId, params] as const,
  },
  subscriptions: {
    current: ["subscription"] as const,
    usage: ["subscription", "usage"] as const,
    billing: ["subscription", "billing"] as const,
    invoices: ["subscription", "invoices"] as const,
    plans: ["subscription", "plans"] as const,
  },
  dashboardStats: {
    home: (projectId: string | null) =>
      ["dashboardStats", projectId] as const,
  },
};
