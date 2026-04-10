import { client } from "@/lib/api/client";
import {
  listSessions,
  getSession,
  deleteSession,
  getSessionAnalytics,
} from "@/lib/api/sessions";

jest.mock("axios", () => {
  const mockAxios = {
    create: jest.fn(() => mockAxios),
    get: jest.fn(),
    post: jest.fn(),
    patch: jest.fn(),
    delete: jest.fn(),
    interceptors: {
      request: { use: jest.fn() },
      response: { use: jest.fn() },
    },
  };
  return { ...mockAxios, default: mockAxios };
});

const mockClient = client as unknown as {
  get: jest.Mock;
  delete: jest.Mock;
};

describe("sessions API", () => {
  beforeEach(() => jest.clearAllMocks());

  it("listSessions gets /sessions", async () => {
    mockClient.get.mockResolvedValue({
      data: { items: [], total: 0, limit: 50, offset: 0 },
    });
    await listSessions({ limit: 10 });
    expect(mockClient.get).toHaveBeenCalledWith("/sessions", {
      params: { limit: 10 },
    });
  });

  it("getSession gets /sessions/:id", async () => {
    mockClient.get.mockResolvedValue({ data: { session_id: "s1" } });
    await getSession("s1", { limit: 100 });
    expect(mockClient.get).toHaveBeenCalledWith("/sessions/s1", {
      params: { limit: 100 },
    });
  });

  it("deleteSession deletes /sessions/:id", async () => {
    mockClient.delete.mockResolvedValue({ data: { deleted: 5 } });
    const result = await deleteSession("s1");
    expect(mockClient.delete).toHaveBeenCalledWith("/sessions/s1");
    expect(result.deleted).toBe(5);
  });

  it("getSessionAnalytics gets /sessions/analytics", async () => {
    mockClient.get.mockResolvedValue({ data: [] });
    await getSessionAnalytics({
      started_after: "2024-01-01",
      started_before: "2024-01-31",
    });
    expect(mockClient.get).toHaveBeenCalledWith("/sessions/analytics", {
      params: { started_after: "2024-01-01", started_before: "2024-01-31" },
    });
  });
});
