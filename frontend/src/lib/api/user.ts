import { client } from "./client";
import type { UserProfileResponse } from "./types";

export async function getProfile(): Promise<UserProfileResponse> {
  const res = await client.get<UserProfileResponse>("/user");
  return res.data;
}
