"use client";

import {
  createContext,
  useContext,
  useEffect,
  useState,
  useCallback,
  type ReactNode,
} from "react";
import { useAuth } from "./AuthProvider";
import { listOrganizations } from "@/lib/api/organizations";
import type { MyOrganizationResponse } from "@/lib/api/types";

interface OrganizationContextValue {
  organizations: MyOrganizationResponse[];
  currentOrg: MyOrganizationResponse | null;
  setCurrentOrg: (org: MyOrganizationResponse) => void;
  loading: boolean;
  refetch: () => Promise<void>;
}

const OrganizationContext = createContext<OrganizationContextValue | null>(null);

const STORAGE_KEY = "pandaprobe_current_org_id";

export function OrganizationProvider({ children }: { children: ReactNode }) {
  const { user, loading: authLoading, authEnabled } = useAuth();
  const [organizations, setOrganizations] = useState<MyOrganizationResponse[]>(
    []
  );
  const [currentOrg, setCurrentOrgState] =
    useState<MyOrganizationResponse | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchOrgs = useCallback(async () => {
    try {
      const orgs = await listOrganizations();
      setOrganizations(orgs);

      const savedId =
        typeof window !== "undefined"
          ? localStorage.getItem(STORAGE_KEY)
          : null;
      const saved = orgs.find((o) => o.id === savedId);
      setCurrentOrgState(saved ?? orgs[0] ?? null);
    } catch {
      setOrganizations([]);
      setCurrentOrgState(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (authLoading) return;
    if (authEnabled && !user) {
      setLoading(false);
      return;
    }
    fetchOrgs();
  }, [user, authLoading, authEnabled, fetchOrgs]);

  const setCurrentOrg = useCallback((org: MyOrganizationResponse) => {
    setCurrentOrgState(org);
    if (typeof window !== "undefined") {
      localStorage.setItem(STORAGE_KEY, org.id);
    }
  }, []);

  return (
    <OrganizationContext.Provider
      value={{ organizations, currentOrg, setCurrentOrg, loading, refetch: fetchOrgs }}
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
