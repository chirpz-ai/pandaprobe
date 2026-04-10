import axios, {
  type AxiosInstance,
  type InternalAxiosRequestConfig,
} from "axios";
import { API_URL } from "@/lib/utils/constants";

let getToken: (() => Promise<string | null>) | null = null;
let getOrgId: (() => string | null) | null = null;
let getProjectId: (() => string | null) | null = null;
let onUnauthorized: (() => void) | null = null;

export function configureAuth(opts: {
  getToken: () => Promise<string | null>;
  getOrgId: () => string | null;
  getProjectId: () => string | null;
  onUnauthorized: () => void;
}) {
  getToken = opts.getToken;
  getOrgId = opts.getOrgId;
  getProjectId = opts.getProjectId;
  onUnauthorized = opts.onUnauthorized;
}

const client: AxiosInstance = axios.create({
  baseURL: API_URL,
  headers: { "Content-Type": "application/json" },
});

client.interceptors.request.use(async (config: InternalAxiosRequestConfig) => {
  if (getToken) {
    const token = await getToken();
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
  }

  if (getOrgId) {
    const orgId = getOrgId();
    if (orgId) {
      config.headers["X-Organization-ID"] = orgId;
    }
  }

  if (getProjectId) {
    const projectId = getProjectId();
    if (projectId) {
      config.headers["X-Project-ID"] = projectId;
    }
  }

  return config;
});

let isRefreshing = false;

client.interceptors.response.use(
  (response) => response,
  async (error) => {
    const original = error.config;
    if (
      error.response?.status === 401 &&
      !original._retry &&
      getToken
    ) {
      if (isRefreshing) {
        return Promise.reject(error);
      }
      original._retry = true;
      isRefreshing = true;
      try {
        const token = await getToken();
        if (token) {
          original.headers.Authorization = `Bearer ${token}`;
          return client(original);
        }
      } catch {
        onUnauthorized?.();
      } finally {
        isRefreshing = false;
      }
    }

    if (error.response?.status === 401) {
      onUnauthorized?.();
    }

    return Promise.reject(error);
  }
);

export { client };

export interface ApiError {
  detail: string;
  errors?: Array<{ loc: string[]; msg: string; type: string }>;
}

export function extractErrorMessage(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const data = error.response?.data as ApiError | undefined;
    if (data?.detail) return data.detail;
    if (error.message) return error.message;
  }
  if (error instanceof Error) return error.message;
  return "An unexpected error occurred";
}
