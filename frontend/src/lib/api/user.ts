import { client } from "./client";
import type {
  InvitationResponse,
  MembershipResponse,
  UserProfileResponse,
} from "./types";

export async function getProfile(): Promise<UserProfileResponse> {
  const res = await client.get<UserProfileResponse>("/me");
  return res.data;
}

export async function listMyInvitations(): Promise<InvitationResponse[]> {
  const res = await client.get<InvitationResponse[]>("/me/invitations");
  return res.data;
}

export async function acceptInvitation(
  invitationId: string,
): Promise<MembershipResponse> {
  const res = await client.post<MembershipResponse>(
    `/me/invitations/${invitationId}/accept`,
  );
  return res.data;
}

export async function declineInvitation(
  invitationId: string,
): Promise<void> {
  await client.post(`/me/invitations/${invitationId}/decline`);
}
