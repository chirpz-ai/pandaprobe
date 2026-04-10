import { client } from "./client";

export interface HealthResponse {
  status: string;
  version?: string;
  environment?: string;
  timestamp?: string;
}

export async function checkHealth(): Promise<HealthResponse> {
  const res = await client.get<HealthResponse>("/health");
  return res.data;
}
