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

import { renderHook } from "@testing-library/react";
import { useAuth } from "@/components/providers/AuthProvider";

describe("AuthProvider", () => {
  it("useAuth throws when used outside AuthProvider", () => {
    jest.spyOn(console, "error").mockImplementation();
    expect(() => renderHook(() => useAuth())).toThrow(
      "useAuth must be used within an AuthProvider",
    );
    jest.restoreAllMocks();
  });
});
