"use client";

import { useEffect, useRef, type ReactNode } from "react";
import { useParams } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import { useAuth } from "./AuthProvider";
import { configureAuth } from "@/lib/api/client";
import { getCurrentToken } from "@/lib/auth/auth-service";

export function ApiConfigProvider({ children }: { children: ReactNode }) {
  const { user, authEnabled } = useAuth();
  const queryClient = useQueryClient();
  const params = useParams();
  const orgId = params.orgId as string | undefined;
  const projectId = params.projectId as string | undefined;

  const uid = user?.uid ?? null;
  const prevUidRef = useRef<string | null>(null);

  useEffect(() => {
    if (prevUidRef.current !== null && prevUidRef.current !== uid) {
      queryClient.clear();
    }
    prevUidRef.current = uid;
  }, [uid, queryClient]);

  useEffect(() => {
    configureAuth({
      getToken: async () => {
        if (!authEnabled) return null;
        return getCurrentToken();
      },
      forceRefreshToken: async () => {
        if (!authEnabled) return null;
        return getCurrentToken(true);
      },
      getOrgId: () => orgId ?? null,
      getProjectId: () => projectId ?? null,
      onUnauthorized: () => {
        if (authEnabled && typeof window !== "undefined") {
          window.location.href = "/login";
        }
      },
    });
  }, [authEnabled, orgId, projectId]);

  return <>{children}</>;
}
