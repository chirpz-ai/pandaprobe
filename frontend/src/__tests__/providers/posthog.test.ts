jest.mock("posthog-js", () => ({
  init: jest.fn(),
  register: jest.fn(),
  identify: jest.fn(),
  reset: jest.fn(),
  capture: jest.fn(),
}));

jest.mock("next/navigation", () => ({
  usePathname: jest.fn(() => "/"),
  useSearchParams: jest.fn(() => ({ toString: () => "" })),
}));

jest.mock("@/components/providers/AuthProvider", () => ({
  useAuth: jest.fn(() => ({
    user: null,
    loading: false,
    authEnabled: true,
  })),
}));

describe("isPostHogEnabled", () => {
  const originalEnv = process.env;

  beforeEach(() => {
    jest.resetModules();
    process.env = { ...originalEnv };
  });

  afterAll(() => {
    process.env = originalEnv;
  });

  it("returns true when auth is enabled and key is set", async () => {
    process.env.NEXT_PUBLIC_POSTHOG_KEY = "phc_test_key";
    const { isPostHogEnabled } =
      await import("@/components/providers/PostHogProvider");
    expect(isPostHogEnabled(true)).toBe(true);
  });

  it("returns false when auth is disabled", async () => {
    process.env.NEXT_PUBLIC_POSTHOG_KEY = "phc_test_key";
    const { isPostHogEnabled } =
      await import("@/components/providers/PostHogProvider");
    expect(isPostHogEnabled(false)).toBe(false);
  });

  it("returns false when key is empty", async () => {
    process.env.NEXT_PUBLIC_POSTHOG_KEY = "";
    const { isPostHogEnabled } =
      await import("@/components/providers/PostHogProvider");
    expect(isPostHogEnabled(true)).toBe(false);
  });

  it("returns false when key is not set", async () => {
    delete process.env.NEXT_PUBLIC_POSTHOG_KEY;
    const { isPostHogEnabled } =
      await import("@/components/providers/PostHogProvider");
    expect(isPostHogEnabled(true)).toBe(false);
  });

  it("returns false when both auth is disabled and key is missing", async () => {
    delete process.env.NEXT_PUBLIC_POSTHOG_KEY;
    const { isPostHogEnabled } =
      await import("@/components/providers/PostHogProvider");
    expect(isPostHogEnabled(false)).toBe(false);
  });
});
