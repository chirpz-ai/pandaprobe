"use client";

import {
  createContext,
  useContext,
  useEffect,
  useState,
  useCallback,
  type ReactNode,
} from "react";
import { useParams, useRouter } from "next/navigation";
import { useAuth } from "./AuthProvider";
import { listOrganizations } from "@/lib/api/organizations";
import { listProjects } from "@/lib/api/projects";
import type { MyOrganizationResponse, ProjectResponse } from "@/lib/api/types";

interface OrganizationContextValue {
  organizations: MyOrganizationResponse[];
  currentOrg: MyOrganizationResponse | null;
  projects: ProjectResponse[];
  loading: boolean;
  refetchOrgs: () => Promise<void>;
  refetchProjects: () => Promise<void>;
}

const OrganizationContext = createContext<OrganizationContextValue | null>(null);

export function OrganizationProvider({ children }: { children: ReactNode }) {
  const params = useParams();
  const router = useRouter();
  const orgId = params.orgId as string;
  const { user, loading: authLoading, authEnabled } = useAuth();

  const [organizations, setOrganizations] = useState<
    MyOrganizationResponse[]
  >([]);
  const [projects, setProjects] = useState<ProjectResponse[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchOrgs = useCallback(async () => {
    try {
      const orgs = await listOrganizations();
      setOrganizations(orgs);

      if (orgId && !orgs.some((o) => o.id === orgId)) {
        router.replace("/");
        return;
      }
    } catch {
      setOrganizations([]);
    }
  }, [orgId, router]);

  const fetchProjects = useCallback(async () => {
    if (!orgId) return;
    try {
      const p = await listProjects(orgId);
      setProjects(p);
    } catch {
      setProjects([]);
    }
  }, [orgId]);

  useEffect(() => {
    if (authLoading) return;
    if (authEnabled && !user) return;

    let cancelled = false;
    async function load() {
      await Promise.all([fetchOrgs(), fetchProjects()]);
      if (!cancelled) setLoading(false);
    }
    load();
    return () => {
      cancelled = true;
    };
  }, [user, authLoading, authEnabled, fetchOrgs, fetchProjects]);

  const currentOrg = organizations.find((o) => o.id === orgId) ?? null;

  return (
    <OrganizationContext.Provider
      value={{
        organizations,
        currentOrg,
        projects,
        loading,
        refetchOrgs: fetchOrgs,
        refetchProjects: fetchProjects,
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
      "useOrganization must be used within an OrganizationProvider"
    );
  }
  return context;
}
