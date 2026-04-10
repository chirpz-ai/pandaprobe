"use client";

import { useEffect, type ReactNode } from "react";
import { useAuth } from "./AuthProvider";
import { useOrganization } from "./OrganizationProvider";
import { useProject } from "./ProjectProvider";
import { configureAuth } from "@/lib/api/client";
import { getCurrentToken } from "@/lib/auth/auth-service";

export function ApiConfigProvider({ children }: { children: ReactNode }) {
  const { authEnabled } = useAuth();
  const { currentOrg } = useOrganization();
  const { currentProject } = useProject();

  useEffect(() => {
    configureAuth({
      getToken: async () => {
        if (!authEnabled) return null;
        return getCurrentToken();
      },
      getOrgId: () => currentOrg?.id ?? null,
      getProjectId: () => currentProject?.id ?? null,
      onUnauthorized: () => {
        if (authEnabled && typeof window !== "undefined") {
          window.location.href = "/login";
        }
      },
    });
  }, [authEnabled, currentOrg, currentProject]);

  return <>{children}</>;
}
