import { queryKeys } from "@/lib/query/keys";

describe("queryKeys", () => {
  it("organizations.all is stable", () => {
    expect(queryKeys.organizations.all).toEqual(["organizations"]);
  });

  it("projects.all includes orgId", () => {
    expect(queryKeys.projects.all("org-1")).toEqual(["projects", "org-1"]);
  });

  it("traces.list includes projectId and params", () => {
    const params = { limit: 50, offset: 0 };
    expect(queryKeys.traces.list("proj-1", params)).toEqual([
      "traces",
      "proj-1",
      params,
    ]);
  });

  it("evaluations.traceRuns.all includes projectId", () => {
    expect(queryKeys.evaluations.traceRuns.all("proj-1")).toEqual([
      "traceRuns",
      "proj-1",
    ]);
  });

  it("evaluations.traceRuns.list includes params", () => {
    const params = { limit: 50, offset: 0 };
    expect(queryKeys.evaluations.traceRuns.list("proj-1", params)).toEqual([
      "traceRuns",
      "proj-1",
      params,
    ]);
  });

  it("subscriptions keys include orgId", () => {
    expect(queryKeys.subscriptions.current("org-1")).toEqual([
      "subscription",
      "org-1",
    ]);
    expect(queryKeys.subscriptions.usage("org-1")).toEqual([
      "subscription",
      "org-1",
      "usage",
    ]);
  });
});
