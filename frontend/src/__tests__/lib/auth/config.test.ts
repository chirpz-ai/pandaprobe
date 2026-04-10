describe("auth config", () => {
  const originalEnv = process.env;

  beforeEach(() => {
    jest.resetModules();
    process.env = { ...originalEnv };
  });

  afterAll(() => {
    process.env = originalEnv;
  });

  it("AUTH_ENABLED defaults to true when env flag is not set", async () => {
    delete process.env.NEXT_PUBLIC_AUTH_ENABLED;
    const { AUTH_ENABLED } = await import("@/lib/auth/config");
    expect(AUTH_ENABLED).toBe(true);
  });

  it("AUTH_ENABLED is false when flag=false in development", async () => {
    Object.defineProperty(process.env, "NODE_ENV", {
      value: "development",
      writable: true,
      configurable: true,
    });
    process.env.NEXT_PUBLIC_AUTH_ENABLED = "false";
    const { AUTH_ENABLED } = await import("@/lib/auth/config");
    expect(AUTH_ENABLED).toBe(false);
  });

  it("SESSION_COOKIE_NAME is __pp_session", async () => {
    const { SESSION_COOKIE_NAME } = await import("@/lib/auth/config");
    expect(SESSION_COOKIE_NAME).toBe("__pp_session");
  });
});
