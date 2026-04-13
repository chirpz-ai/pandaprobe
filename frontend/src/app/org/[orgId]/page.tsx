"use client";

import { useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import { useOrganization } from "@/components/providers/OrganizationProvider";
import { useResolvedProjectId } from "@/hooks/useNavigation";
import { Spinner } from "@/components/ui/Spinner";

export default function OrgPage() {
  const { orgId } = useParams();
  const router = useRouter();
  const { projects, loading } = useOrganization();
  const projectId = useResolvedProjectId(projects);

  useEffect(() => {
    if (loading) return;

    if (projectId) {
      router.replace(`/org/${orgId}/project/${projectId}`);
    }
  }, [orgId, projectId, loading, router]);

  return (
    <div className="flex h-full items-center justify-center">
      {!loading && projects.length === 0 ? (
        <div className="text-center space-y-2">
          <p className="text-sm font-mono text-text-dim">No projects yet.</p>
          <p className="text-xs font-mono text-text-muted">
            Create a project in Settings to get started.
          </p>
        </div>
      ) : (
        <Spinner size="lg" />
      )}
    </div>
  );
}
