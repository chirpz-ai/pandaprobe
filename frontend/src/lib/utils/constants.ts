export const DEFAULT_PAGE_SIZE = 50;
export const MAX_PAGE_SIZE = 200;

export const API_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export const DOCS_URL = "https://docs.pandaprobe.com";
export const DOCS_QUICKSTART_URL = `${DOCS_URL}/get-started/quickstart`;
export const DOCS_TRACING_URL = `${DOCS_URL}/tracing/overview`;
export const DOCS_INTEGRATIONS_URL = `${DOCS_URL}/tracing/integrations/overview`;
export const DOCS_MANUAL_URL = `${DOCS_URL}/tracing/manual/decorators`;
export const DOCS_CONCEPTS_URL = `${DOCS_URL}/tracing/concepts`;

export const DOCS_EVAL_CONCEPTS_URL = `${DOCS_URL}/evaluation/get-started/concepts`;
export const DOCS_EVAL_APPROACHES_URL = `${DOCS_URL}/evaluation/get-started/evaluation-approaches`;
export const DOCS_EVAL_API_URL = `${DOCS_URL}/evaluation/setup/run-eval-api`;
export const DOCS_EVAL_UI_URL = `${DOCS_URL}/evaluation/setup/run-eval-ui`;
export const DOCS_EVAL_SCHEDULING_URL = `${DOCS_URL}/evaluation/setup/scheduling`;

export const STORAGE_KEYS = {
  orgId: "pandaprobe_current_org_id",
  projectId: "pp_project_id",
} as const;

export function clearUserStorage() {
  localStorage.removeItem(STORAGE_KEYS.orgId);
  localStorage.removeItem(STORAGE_KEYS.projectId);
}
