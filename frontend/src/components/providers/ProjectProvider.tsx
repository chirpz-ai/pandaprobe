"use client";

import {
  createContext,
  useContext,
  useEffect,
  type ReactNode,
} from "react";
import { useParams, useRouter } from "next/navigation";
import { useOrganization } from "./OrganizationProvider";
import type { ProjectResponse } from "@/lib/api/types";

interface ProjectContextValue {
  currentProject: ProjectResponse | null;
}

const ProjectContext = createContext<ProjectContextValue | null>(null);

const STORAGE_KEY = "pp_project_id";

export function ProjectProvider({ children }: { children: ReactNode }) {
  const params = useParams();
  const router = useRouter();
  const orgId = params.orgId as string;
  const projectId = params.projectId as string;
  const { projects, loading: orgLoading } = useOrganization();

  const currentProject = projects.find((p) => p.id === projectId) ?? null;

  useEffect(() => {
    if (orgLoading || projects.length === 0) return;

    if (projectId && !projects.some((p) => p.id === projectId)) {
      router.replace(`/org/${orgId}`);
      return;
    }

    if (projectId) {
      localStorage.setItem(STORAGE_KEY, projectId);
    }
  }, [projectId, projects, orgLoading, orgId, router]);

  return (
    <ProjectContext.Provider value={{ currentProject }}>
      {children}
    </ProjectContext.Provider>
  );
}

export function useProject(): ProjectContextValue {
  const context = useContext(ProjectContext);
  if (!context) {
    throw new Error("useProject must be used within a ProjectProvider");
  }
  return context;
}
