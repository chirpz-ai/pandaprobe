export const DEFAULT_PAGE_SIZE = 50;
export const MAX_PAGE_SIZE = 200;

export const API_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export const STORAGE_KEYS = {
  orgId: "pandaprobe_current_org_id",
  projectId: "pp_project_id",
} as const;

export function clearUserStorage() {
  localStorage.removeItem(STORAGE_KEYS.orgId);
  localStorage.removeItem(STORAGE_KEYS.projectId);
}
