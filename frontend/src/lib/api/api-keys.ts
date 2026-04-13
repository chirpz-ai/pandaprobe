import { client } from "./client";
import type { CreateAPIKeyRequest, APIKeyResponse } from "./types";

export async function createAPIKey(
  orgId: string,
  data: CreateAPIKeyRequest,
): Promise<APIKeyResponse> {
  const res = await client.post<APIKeyResponse>(
    `/organizations/${orgId}/api-keys`,
    data,
  );
  return res.data;
}

export async function listAPIKeys(orgId: string): Promise<APIKeyResponse[]> {
  const res = await client.get<APIKeyResponse[]>(
    `/organizations/${orgId}/api-keys`,
  );
  return res.data;
}

export async function getAPIKey(
  orgId: string,
  keyId: string,
): Promise<APIKeyResponse> {
  const res = await client.get<APIKeyResponse>(
    `/organizations/${orgId}/api-keys/${keyId}`,
  );
  return res.data;
}

export async function rotateAPIKey(
  orgId: string,
  keyId: string,
): Promise<APIKeyResponse> {
  const res = await client.post<APIKeyResponse>(
    `/organizations/${orgId}/api-keys/${keyId}/rotate`,
  );
  return res.data;
}

export async function deleteAPIKey(
  orgId: string,
  keyId: string,
  permanent = false,
): Promise<void> {
  await client.delete(`/organizations/${orgId}/api-keys/${keyId}`, {
    params: { permanent },
  });
}
