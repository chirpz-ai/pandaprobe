jest.mock("@/lib/auth/firebase", () => ({
  AUTH_ENABLED: true,
}));

jest.mock("@/lib/auth/auth-service", () => ({
  signInWithGoogle: jest.fn(),
  signInWithEmail: jest.fn(),
  signUpWithEmail: jest.fn(),
  signOut: jest.fn(),
  getCurrentToken: jest.fn(),
  onIdTokenChanged: jest.fn(() => jest.fn()),
  setSessionCookie: jest.fn(),
  clearSessionCookie: jest.fn(),
}));

jest.mock("@/lib/utils/constants", () => ({
  clearUserStorage: jest.fn(),
}));

jest.mock("next/navigation", () => ({
  useParams: jest.fn(() => ({ orgId: "org-1" })),
  useRouter: jest.fn(() => ({ replace: jest.fn() })),
}));

jest.mock("@/lib/api/organizations", () => ({
  listOrganizations: jest.fn(),
}));

jest.mock("@/lib/api/projects", () => ({
  listProjects: jest.fn(),
}));

import { renderHook } from "@testing-library/react";
import { useOrganization } from "@/components/providers/OrganizationProvider";

describe("OrganizationProvider", () => {
  it("useOrganization throws when used outside OrganizationProvider", () => {
    jest.spyOn(console, "error").mockImplementation();
    expect(() => renderHook(() => useOrganization())).toThrow(
      "useOrganization must be used within an OrganizationProvider",
    );
    jest.restoreAllMocks();
  });
});
