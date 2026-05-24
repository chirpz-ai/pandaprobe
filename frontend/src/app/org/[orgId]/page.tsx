"use client";

import { useEffect } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { ArrowRight, FolderPlus } from "lucide-react";
import { useOrganization } from "@/components/providers/OrganizationProvider";
import { useResolvedProjectId } from "@/hooks/useNavigation";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";
import { Spinner } from "@/components/ui/Spinner";

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

  // Edge case: user lands here with zero projects.
  const projectsHref = `/org/${orgId as string}/settings/projects`;

  return (
    <div className="max-w-2xl mx-auto py-8 px-4 space-y-6 animate-fade-in">
      <div>
        <h1 className="text-lg font-mono text-primary">
          Welcome to PandaProbe
        </h1>
        <p className="text-sm font-mono text-text-dim mt-1">
          Create your first project to start tracing your AI agents.
        </p>
      </div>

      <section
        className="border-engraved bg-surface"
        aria-label="Create your first project"
      >
        <div className="flex items-center gap-4 px-5 py-4">
          <span className="flex-shrink-0 flex items-center justify-center h-10 w-10 border border-primary/40 bg-primary/10 text-primary">
            <FolderPlus className="h-4 w-4" />
          </span>
          <div className="flex-1 min-w-0">
            <h2 className="text-sm font-mono text-text">Create a project</h2>
            <p className="text-xs font-mono text-text-muted mt-0.5 leading-snug">
              Projects isolate traces, sessions, and evaluations. Once
              you&apos;ve created one, we&apos;ll walk you through sending your
              first trace.
            </p>
          </div>
          <Link
            href={projectsHref}
            className="flex-shrink-0 inline-flex items-center gap-1.5 px-3 py-1.5 border border-info/40 bg-info/10 text-xs font-mono text-info hover:bg-info/20 transition-colors"
          >
            Create project
            <ArrowRight className="h-3 w-3" />
          </Link>
        </div>
      </section>
    </div>
  );
}
