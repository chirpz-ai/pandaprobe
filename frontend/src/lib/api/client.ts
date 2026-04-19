import axios, {
  type AxiosInstance,
  type InternalAxiosRequestConfig,
} from "axios";
import { API_URL } from "@/lib/utils/constants";

let getToken: (() => Promise<string | null>) | null = null;
let forceRefreshToken: (() => Promise<string | null>) | null = null;
let getOrgId: (() => string | null) | null = null;
let getProjectId: (() => string | null) | null = null;
let onUnauthorized: (() => void) | null = null;

export function configureAuth(opts: {
  getToken: () => Promise<string | null>;
  forceRefreshToken: () => Promise<string | null>;
  getOrgId: () => string | null;
  getProjectId: () => string | null;
  onUnauthorized: () => void;
}) {
  getToken = opts.getToken;
  forceRefreshToken = opts.forceRefreshToken;
  getOrgId = opts.getOrgId;
  getProjectId = opts.getProjectId;
  onUnauthorized = opts.onUnauthorized;
}

const client: AxiosInstance = axios.create({
  baseURL: API_URL,
  headers: { "Content-Type": "application/json" },
  paramsSerializer: {
    indexes: null,
  },
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

let refreshPromise: Promise<string | null> | null = null;

client.interceptors.response.use(
  (response) => response,
  async (error) => {
    const original = error.config;
    if (
      error.response?.status === 401 &&
      !original._retry &&
      forceRefreshToken
    ) {
      original._retry = true;

      if (!refreshPromise) {
        refreshPromise = forceRefreshToken().finally(() => {
          refreshPromise = null;
        });
      }

      try {
        const token = await refreshPromise;
        if (token) {
          original.headers.Authorization = `Bearer ${token}`;
          return client(original);
        }
      } catch {
        onUnauthorized?.();
        return Promise.reject(error);
      }
    }

    if (error.response?.status === 401) {
      onUnauthorized?.();
    }

    return Promise.reject(error);
  },
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
