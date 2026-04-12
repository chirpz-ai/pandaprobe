"use client";

import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  type ReactNode,
} from "react";
import { useParams, useRouter } from "next/navigation";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useAuth } from "./AuthProvider";
import { listOrganizations } from "@/lib/api/organizations";
import { listProjects } from "@/lib/api/projects";
import { queryKeys } from "@/lib/query/keys";
import type { MyOrganizationResponse, ProjectResponse } from "@/lib/api/types";

interface OrganizationContextValue {
  organizations: MyOrganizationResponse[];
  currentOrg: MyOrganizationResponse | null;
  projects: ProjectResponse[];
  loading: boolean;
  refetchOrgs: () => void;
  refetchProjects: () => void;
}

const OrganizationContext = createContext<OrganizationContextValue | null>(
  null,
);

export function OrganizationProvider({ children }: { children: ReactNode }) {
  const params = useParams();
  const router = useRouter();
  const queryClient = useQueryClient();
  const orgId = params.orgId as string;
  const { user, loading: authLoading, authEnabled } = useAuth();

  const authReady = !authLoading && (!authEnabled || !!user);

  const orgsQuery = useQuery({
    queryKey: queryKeys.organizations.list(),
    queryFn: listOrganizations,
    enabled: authReady,
  });

  const projectsQuery = useQuery({
    queryKey: queryKeys.projects.list(orgId),
    queryFn: () => listProjects(orgId),
    enabled: authReady && !!orgId,
  });

  const organizations = useMemo(() => orgsQuery.data ?? [], [orgsQuery.data]);
  const projects = useMemo(
    () => projectsQuery.data ?? [],
    [projectsQuery.data],
  );
  const loading = orgsQuery.isPending || projectsQuery.isPending;
  const currentOrg = useMemo(
    () => organizations.find((o) => o.id === orgId) ?? null,
    [organizations, orgId],
  );

  useEffect(() => {
    if (
      orgsQuery.isSuccess &&
      orgId &&
      !organizations.some((o) => o.id === orgId)
    ) {
      router.replace("/");
    }
  }, [orgsQuery.isSuccess, orgId, organizations, router]);

  function refetchOrgs() {
    queryClient.invalidateQueries({ queryKey: queryKeys.organizations.all });
  }

  function refetchProjects() {
    queryClient.invalidateQueries({
      queryKey: queryKeys.projects.all(orgId),
    });
  }

  return (
    <OrganizationContext.Provider
      value={{
        organizations,
        currentOrg,
        projects,
        loading,
        refetchOrgs,
        refetchProjects,
      }}
    >
      {children}
    </OrganizationContext.Provider>
  );
}

export function useOrganization(): OrganizationContextValue {
  const context = useContext(OrganizationContext);
  if (!context) {
    throw new Error(
      "useOrganization must be used within an OrganizationProvider",
    );
  }
  return context;
}
