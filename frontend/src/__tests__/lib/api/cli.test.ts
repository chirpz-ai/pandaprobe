import { client } from "@/lib/api/client";
import { createCliAuthCode } from "@/lib/api/cli";

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
  post: jest.Mock;
};

describe("cli auth API", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("createCliAuthCode posts the org/project + PKCE challenge to /cli/auth/codes", async () => {
    const payload = {
      org_id: "org-1",
      project_id: "proj-1",
      code_challenge: "challenge-abc",
      code_challenge_method: "S256" as const,
      label: "laptop",
      expires_days: 90,
    };
    mockClient.post.mockResolvedValue({
      data: { code: "the-code", expires_in: 120 },
    });

    const result = await createCliAuthCode(payload);

    expect(mockClient.post).toHaveBeenCalledWith("/cli/auth/codes", payload);
    expect(result).toEqual({ code: "the-code", expires_in: 120 });
  });
});
