"use client";

import { useParams } from "next/navigation";

export function useOrgId(): string {
  const params = useParams();
  return params.orgId as string;
}

export function useProjectId(): string | undefined {
  const params = useParams();
  return params.projectId as string | undefined;
}

export function useOrgPath(path = ""): string {
  return `/org/${useOrgId()}${path}`;
}

export function useProjectPath(path = ""): string {
  const params = useParams();
  return `/org/${params.orgId}/project/${params.projectId}${path}`;
}

const PROJECT_STORAGE_KEY = "pp_project_id";

export function useResolvedProjectId(
  projects: { id: string }[]
): string | null {
  const projectIdFromUrl = useProjectId();
  if (projectIdFromUrl) return projectIdFromUrl;
  if (typeof window !== "undefined") {
    const saved = localStorage.getItem(PROJECT_STORAGE_KEY);
    if (saved && projects.some((p) => p.id === saved)) return saved;
  }
  return projects[0]?.id ?? null;
}
