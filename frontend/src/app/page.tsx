"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Loader2 } from "lucide-react";
import { useAuth } from "@/components/providers/AuthProvider";
import { getProfile } from "@/lib/api/user";
import { listOrganizations, createOrganization } from "@/lib/api/organizations";
import { extractErrorMessage } from "@/lib/api/client";
import { STORAGE_KEYS } from "@/lib/utils/constants";
import { Spinner } from "@/components/ui/Spinner";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";

export default function RootPage() {
  const router = useRouter();
  const { user, loading: authLoading, authEnabled } = useAuth();
  const [error, setError] = useState<string | null>(null);
  const [noOrgs, setNoOrgs] = useState(false);
  const [newOrgName, setNewOrgName] = useState("");
  const [creating, setCreating] = useState(false);

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
          setNoOrgs(true);
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

  async function handleCreateOrg() {
    if (!newOrgName.trim()) return;
    setCreating(true);
    setError(null);
    try {
      const org = await createOrganization({ name: newOrgName.trim() });
      localStorage.setItem(STORAGE_KEYS.orgId, org.id);
      router.replace(`/org/${org.id}`);
    } catch (err) {
      setError(extractErrorMessage(err));
      setCreating(false);
    }
  }

  if (noOrgs) {
    return (
      <div className="flex h-screen w-full items-center justify-center bg-bg">
        <div className="w-full max-w-sm space-y-4 border border-border bg-surface p-6">
          <h1 className="text-sm font-mono text-primary">
            Create Your First Organization
          </h1>
          <p className="text-xs font-mono text-text-dim">
            Organizations are workspaces where you manage projects, traces, and
            team members.
          </p>
          <Input
            value={newOrgName}
            onChange={(e) => setNewOrgName(e.target.value)}
            placeholder="Organization name"
            disabled={creating}
            onKeyDown={(e) => {
              if (e.key === "Enter" && newOrgName.trim()) handleCreateOrg();
            }}
            autoFocus
          />
          {error && <p className="text-xs font-mono text-error">{error}</p>}
          <Button
            onClick={handleCreateOrg}
            disabled={creating || !newOrgName.trim()}
            className="w-full"
          >
            {creating && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
            Create
          </Button>
        </div>
      </div>
    );
  }

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
