jest.mock("next/navigation", () => ({
  useParams: jest.fn(() => ({ orgId: "org-1", projectId: "proj-1" })),
  useRouter: jest.fn(() => ({ replace: jest.fn() })),
}));

jest.mock("@/components/providers/OrganizationProvider", () => ({
  useOrganization: jest.fn(() => ({
    projects: [],
    loading: false,
  })),
}));

jest.mock("@/lib/utils/constants", () => ({
  STORAGE_KEYS: { projectId: "pp_projectId" },
}));

import { renderHook } from "@testing-library/react";
import { useProject } from "@/components/providers/ProjectProvider";

describe("ProjectProvider", () => {
  it("useProject throws when used outside ProjectProvider", () => {
    jest.spyOn(console, "error").mockImplementation();
    expect(() => renderHook(() => useProject())).toThrow(
      "useProject must be used within a ProjectProvider",
    );
    jest.restoreAllMocks();
  });
});
