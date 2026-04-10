import { client } from "@/lib/api/client";
import {
  createTrace,
  listTraces,
  getTrace,
  updateTrace,
  deleteTrace,
  batchDeleteTraces,
  batchUpdateTags,
  getTraceAnalytics,
  listTraceUsers,
  createSpans,
  updateSpan,
} from "@/lib/api/traces";

jest.mock("axios", () => {
  const mockAxios: Record<string, unknown> = {
    get: jest.fn(),
    post: jest.fn(),
    patch: jest.fn(),
    delete: jest.fn(),
    interceptors: {
      request: { use: jest.fn() },
      response: { use: jest.fn() },
    },
  };
  mockAxios.create = jest.fn(() => mockAxios);
  return { ...mockAxios, default: mockAxios };
});

const mockClient = client as unknown as {
  get: jest.Mock;
  post: jest.Mock;
  patch: jest.Mock;
  delete: jest.Mock;
};

describe("traces API", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("createTrace posts to /traces", async () => {
    const payload = { name: "test", started_at: "2024-01-01T00:00:00Z" };
    mockClient.post.mockResolvedValue({ data: { trace_id: "abc", task_id: "t1" } });
    const result = await createTrace(payload);
    expect(mockClient.post).toHaveBeenCalledWith("/traces", payload);
    expect(result).toEqual({ trace_id: "abc", task_id: "t1" });
  });

  it("listTraces gets /traces with params", async () => {
    const params = { limit: 10, offset: 0, status: "COMPLETED" as const };
    mockClient.get.mockResolvedValue({
      data: { items: [], total: 0, limit: 10, offset: 0 },
    });
    await listTraces(params);
    expect(mockClient.get).toHaveBeenCalledWith("/traces", { params });
  });

  it("getTrace gets /traces/:id", async () => {
    mockClient.get.mockResolvedValue({ data: { trace_id: "abc" } });
    const result = await getTrace("abc");
    expect(mockClient.get).toHaveBeenCalledWith("/traces/abc");
    expect(result.trace_id).toBe("abc");
  });

  it("updateTrace patches /traces/:id", async () => {
    mockClient.patch.mockResolvedValue({ data: { trace_id: "abc" } });
    await updateTrace("abc", { name: "updated" });
    expect(mockClient.patch).toHaveBeenCalledWith("/traces/abc", { name: "updated" });
  });

  it("deleteTrace deletes /traces/:id", async () => {
    mockClient.delete.mockResolvedValue({});
    await deleteTrace("abc");
    expect(mockClient.delete).toHaveBeenCalledWith("/traces/abc");
  });

  it("batchDeleteTraces posts to /traces/batch/delete", async () => {
    mockClient.post.mockResolvedValue({ data: { deleted: 2 } });
    const result = await batchDeleteTraces({ trace_ids: ["a", "b"] });
    expect(mockClient.post).toHaveBeenCalledWith("/traces/batch/delete", {
      trace_ids: ["a", "b"],
    });
    expect(result.deleted).toBe(2);
  });

  it("batchUpdateTags posts to /traces/batch/tags", async () => {
    mockClient.post.mockResolvedValue({ data: { updated: 3 } });
    await batchUpdateTags({ trace_ids: ["a"], add_tags: ["t1"] });
    expect(mockClient.post).toHaveBeenCalledWith("/traces/batch/tags", {
      trace_ids: ["a"],
      add_tags: ["t1"],
    });
  });

  it("getTraceAnalytics gets /traces/analytics", async () => {
    mockClient.get.mockResolvedValue({ data: [] });
    await getTraceAnalytics({
      metric: "volume",
      started_after: "2024-01-01",
      started_before: "2024-01-31",
    });
    expect(mockClient.get).toHaveBeenCalledWith("/traces/analytics", {
      params: { metric: "volume", started_after: "2024-01-01", started_before: "2024-01-31" },
    });
  });

  it("listTraceUsers gets /traces/users", async () => {
    mockClient.get.mockResolvedValue({
      data: { items: [], total: 0, limit: 50, offset: 0 },
    });
    await listTraceUsers({ limit: 10 });
    expect(mockClient.get).toHaveBeenCalledWith("/traces/users", {
      params: { limit: 10 },
    });
  });

  it("createSpans posts to /traces/:id/spans", async () => {
    mockClient.post.mockResolvedValue({ data: { span_ids: ["s1"] } });
    await createSpans("abc", [{ name: "span1", started_at: "2024-01-01T00:00:00Z" }]);
    expect(mockClient.post).toHaveBeenCalledWith(
      "/traces/abc/spans",
      [{ name: "span1", started_at: "2024-01-01T00:00:00Z" }]
    );
  });

  it("updateSpan patches /traces/:id/spans/:spanId", async () => {
    mockClient.patch.mockResolvedValue({ data: { span_id: "s1" } });
    await updateSpan("abc", "s1", { name: "updated" });
    expect(mockClient.patch).toHaveBeenCalledWith("/traces/abc/spans/s1", {
      name: "updated",
    });
  });
});
