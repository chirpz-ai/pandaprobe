"use client";

import {
  createContext,
  useContext,
  useEffect,
  useState,
  useCallback,
  type ReactNode,
} from "react";
import { useOrganization } from "./OrganizationProvider";
import { listProjects } from "@/lib/api/projects";
import type { ProjectResponse } from "@/lib/api/types";

interface ProjectContextValue {
  projects: ProjectResponse[];
  currentProject: ProjectResponse | null;
  setCurrentProject: (project: ProjectResponse) => void;
  loading: boolean;
  refetch: () => Promise<void>;
}

const ProjectContext = createContext<ProjectContextValue | null>(null);

const STORAGE_KEY = "pandaprobe_current_project_id";

export function ProjectProvider({ children }: { children: ReactNode }) {
  const { currentOrg, loading: orgLoading } = useOrganization();
  const [projects, setProjects] = useState<ProjectResponse[]>([]);
  const [currentProject, setCurrentProjectState] =
    useState<ProjectResponse | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchProjects = useCallback(async () => {
    if (!currentOrg) {
      setProjects([]);
      setCurrentProjectState(null);
      setLoading(false);
      return;
    }
    try {
      setLoading(true);
      const p = await listProjects(currentOrg.id);
      setProjects(p);

      const savedId =
        typeof window !== "undefined"
          ? localStorage.getItem(STORAGE_KEY)
          : null;
      const saved = p.find((proj) => proj.id === savedId);
      setCurrentProjectState(saved ?? p[0] ?? null);
    } catch {
      setProjects([]);
      setCurrentProjectState(null);
    } finally {
      setLoading(false);
    }
  }, [currentOrg]);

  useEffect(() => {
    if (orgLoading) return;
    fetchProjects();
  }, [currentOrg, orgLoading, fetchProjects]);

  const setCurrentProject = useCallback((project: ProjectResponse) => {
    setCurrentProjectState(project);
    if (typeof window !== "undefined") {
      localStorage.setItem(STORAGE_KEY, project.id);
    }
  }, []);

  return (
    <ProjectContext.Provider
      value={{
        projects,
        currentProject,
        setCurrentProject,
        loading,
        refetch: fetchProjects,
      }}
    >
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
