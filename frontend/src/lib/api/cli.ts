import { client } from "./client";

/**
 * CLI login (OAuth2 Authorization Code + PKCE) — web side.
 *
 * The `/cli-login` page calls this to mint a single-use authorization
 * code (B1) for the chosen org/project. The raw API key is never minted
 * here — the CLI exchanges the code + PKCE verifier directly with the
 * backend (B2). The `/cli-login` page is not org-scoped, so the active
 * org/project are passed explicitly in the body rather than via the
 * `X-Organization-ID` / `X-Project-ID` headers the client injects on
 * org-scoped routes.
 */

export interface CreateCliAuthCodeRequest {
  org_id: string;
  project_id: string;
  code_challenge: string;
  code_challenge_method: "S256";
  label: string;
  expires_days: number;
}

export interface CreateCliAuthCodeResponse {
  code: string;
  expires_in: number;
}

export async function createCliAuthCode(
  data: CreateCliAuthCodeRequest,
): Promise<CreateCliAuthCodeResponse> {
  const res = await client.post<CreateCliAuthCodeResponse>(
    "/cli/auth/codes",
    data,
  );
  return res.data;
}
