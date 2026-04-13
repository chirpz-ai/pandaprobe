import { client } from "./client";
import type {
  CreateProjectRequest,
  UpdateProjectRequest,
  ProjectResponse,
} from "./types";

export async function createProject(
  orgId: string,
  data: CreateProjectRequest,
): Promise<ProjectResponse> {
  const res = await client.post<ProjectResponse>(
    `/organizations/${orgId}/projects`,
    data,
  );
  return res.data;
}

export async function listProjects(orgId: string): Promise<ProjectResponse[]> {
  const res = await client.get<ProjectResponse[]>(
    `/organizations/${orgId}/projects`,
  );
  return res.data;
}

export async function getProject(
  orgId: string,
  projectId: string,
): Promise<ProjectResponse> {
  const res = await client.get<ProjectResponse>(
    `/organizations/${orgId}/projects/${projectId}`,
  );
  return res.data;
}

export async function updateProject(
  orgId: string,
  projectId: string,
  data: UpdateProjectRequest,
): Promise<ProjectResponse> {
  const res = await client.patch<ProjectResponse>(
    `/organizations/${orgId}/projects/${projectId}`,
    data,
  );
  return res.data;
}

export async function deleteProject(
  orgId: string,
  projectId: string,
): Promise<void> {
  await client.delete(`/organizations/${orgId}/projects/${projectId}`);
}
