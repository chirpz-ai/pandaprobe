"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/components/providers/AuthProvider";
import { getProfile } from "@/lib/api/user";
import { listOrganizations } from "@/lib/api/organizations";
import { STORAGE_KEYS } from "@/lib/utils/constants";
import { Spinner } from "@/components/ui/Spinner";

export default function RootPage() {
  const router = useRouter();
  const { user, loading: authLoading, authEnabled } = useAuth();
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (authLoading) return;

    if (authEnabled && !user) {
      router.replace("/login");
      return;
    }

    async function resolveOrg() {
      try {
        if (!authEnabled) {
          await getProfile();
        }

        const orgs = await listOrganizations();
        if (orgs.length === 0) {
          setError("No organizations found. Please contact support.");
          return;
        }

        const savedOrgId = localStorage.getItem(STORAGE_KEYS.orgId);
        const match = savedOrgId && orgs.some((o) => o.id === savedOrgId);

        const targetOrg = match ? savedOrgId : orgs[0].id;
        localStorage.setItem(STORAGE_KEYS.orgId, targetOrg);
        router.replace(`/org/${targetOrg}`);
      } catch {
        setError("Failed to load organizations.");
      }
    }

    resolveOrg();
  }, [user, authLoading, authEnabled, router]);

  return (
    <div className="flex h-screen w-full items-center justify-center bg-bg">
      {error ? (
        <p className="text-sm font-mono text-error">{error}</p>
      ) : (
        <Spinner size="lg" />
      )}
    </div>
  );
}
