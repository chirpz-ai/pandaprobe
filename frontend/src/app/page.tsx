"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/components/providers/AuthProvider";
import { listOrganizations } from "@/lib/api/organizations";
import { Spinner } from "@/components/ui/Spinner";

const ORG_STORAGE_KEY = "pandaprobe_current_org_id";

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

    const savedOrgId =
      typeof window !== "undefined"
        ? localStorage.getItem(ORG_STORAGE_KEY)
        : null;

    if (savedOrgId) {
      router.replace(`/org/${savedOrgId}`);
      return;
    }

    listOrganizations()
      .then((orgs) => {
        if (orgs.length > 0) {
          localStorage.setItem(ORG_STORAGE_KEY, orgs[0].id);
          router.replace(`/org/${orgs[0].id}`);
        } else {
          setError("No organizations found. Please contact support.");
        }
      })
      .catch(() => {
        setError("Failed to load organizations.");
      });
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
