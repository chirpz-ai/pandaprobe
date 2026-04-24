jest.mock("@radix-ui/react-toast", () => ({
  Provider: ({ children }: { children: React.ReactNode }) => children,
  Root: ({ children }: { children: React.ReactNode }) => children,
  Title: ({ children }: { children: React.ReactNode }) => children,
  Description: ({ children }: { children: React.ReactNode }) => children,
  Close: ({ children }: { children: React.ReactNode }) => children,
  Viewport: () => null,
}));

jest.mock("lucide-react", () => ({
  X: () => null,
}));

import React from "react";
import { renderHook } from "@testing-library/react";
import {
  useToast,
  CORNER_STACK_SLOT_ID,
} from "@/components/providers/ToastProvider";

describe("ToastProvider", () => {
  it("useToast throws when used outside ToastProvider", () => {
    jest.spyOn(console, "error").mockImplementation();
    expect(() => renderHook(() => useToast())).toThrow(
      "useToast must be used within a ToastProvider",
    );
    jest.restoreAllMocks();
  });

  it("CORNER_STACK_SLOT_ID has the expected value", () => {
    expect(CORNER_STACK_SLOT_ID).toBe("pandaprobe-corner-stack-slot");
  });
});
