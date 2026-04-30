"use client";

import { useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import { useOrganization } from "@/components/providers/OrganizationProvider";
import { useResolvedProjectId } from "@/hooks/useNavigation";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";
import { Spinner } from "@/components/ui/Spinner";
import { OnboardingChecklist } from "@/components/features/OnboardingChecklist";

export default function OrgPage() {
  const { orgId } = useParams();
  const router = useRouter();
  const { projects, loading } = useOrganization();
  const projectId = useResolvedProjectId(projects);

  useDocumentTitle("Welcome");

  useEffect(() => {
    if (loading) return;

    if (projectId) {
      router.replace(`/org/${orgId}/project/${projectId}`);
    }
  }, [orgId, projectId, loading, router]);

  if (loading || projectId) {
    return (
      <div className="flex h-full items-center justify-center">
        <Spinner size="lg" />
      </div>
    );
  }

  return (
    <div className="max-w-3xl mx-auto py-8 px-4 space-y-6 animate-fade-in">
      <div>
        <h1 className="text-lg font-mono text-primary">
          Welcome to PandaProbe
        </h1>
        <p className="text-sm font-mono text-text-dim mt-1">
        Let&apos;s get you set up before you can send traces.
        </p>
      </div>

      <OnboardingChecklist />
    </div>
  );
}
