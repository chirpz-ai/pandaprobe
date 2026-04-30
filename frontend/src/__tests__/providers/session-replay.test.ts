jest.mock("posthog-js", () => ({
  startSessionRecording: jest.fn(),
  stopSessionRecording: jest.fn(),
}));

jest.mock("next/navigation", () => ({
  usePathname: jest.fn(() => "/"),
}));

jest.mock("@/components/providers/AuthProvider", () => ({
  useAuth: jest.fn(() => ({ authEnabled: true })),
}));

jest.mock("@/components/providers/PostHogProvider", () => ({
  isPostHogEnabled: jest.fn(() => true),
}));

import { isBlockedRoute } from "@/components/providers/SessionReplayController";

describe("isBlockedRoute", () => {
  it("blocks /settings/account", () => {
    expect(isBlockedRoute("/settings/account")).toBe(true);
  });

  it("blocks /settings/invitations", () => {
    expect(isBlockedRoute("/settings/invitations")).toBe(true);
  });

  it("allows /settings/api-keys", () => {
    expect(isBlockedRoute("/org/abc/settings/api-keys")).toBe(false);
  });

  it("allows /settings/billing", () => {
    expect(isBlockedRoute("/org/abc/settings/billing")).toBe(false);
  });

  it("allows /settings/plans", () => {
    expect(isBlockedRoute("/org/abc/settings/plans")).toBe(false);
  });

  it("allows /settings/members", () => {
    expect(isBlockedRoute("/org/abc/settings/members")).toBe(false);
  });

  it("allows project home page", () => {
    expect(isBlockedRoute("/org/abc/project/p1")).toBe(false);
  });

  it("allows traces page", () => {
    expect(isBlockedRoute("/org/abc/project/p1/traces")).toBe(false);
  });

  it("allows sessions page", () => {
    expect(isBlockedRoute("/org/abc/project/p1/sessions")).toBe(false);
  });

  it("allows evaluations page", () => {
    expect(isBlockedRoute("/org/abc/project/p1/evaluations")).toBe(false);
  });

  it("allows organization settings page", () => {
    expect(isBlockedRoute("/org/abc/settings")).toBe(false);
  });
});
