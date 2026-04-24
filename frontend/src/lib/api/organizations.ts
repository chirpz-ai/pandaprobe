import { client } from "./client";
import type {
  CreateOrganizationRequest,
  UpdateOrganizationRequest,
  OrganizationResponse,
  MyOrganizationResponse,
  MembershipResponse,
  UpdateMemberRoleRequest,
  CreateInvitationRequest,
  InvitationResponse,
} from "./types";

export async function createOrganization(
  data: CreateOrganizationRequest,
): Promise<OrganizationResponse> {
  const res = await client.post<OrganizationResponse>("/organizations", data);
  return res.data;
}

export async function listOrganizations(): Promise<MyOrganizationResponse[]> {
  const res = await client.get<MyOrganizationResponse[]>("/organizations");
  return res.data;
}

export async function getOrganization(
  orgId: string,
): Promise<MyOrganizationResponse> {
  const res = await client.get<MyOrganizationResponse>(
    `/organizations/${orgId}`,
  );
  return res.data;
}

export async function updateOrganization(
  orgId: string,
  data: UpdateOrganizationRequest,
): Promise<OrganizationResponse> {
  const res = await client.patch<OrganizationResponse>(
    `/organizations/${orgId}`,
    data,
  );
  return res.data;
}

export async function deleteOrganization(orgId: string): Promise<void> {
  await client.delete(`/organizations/${orgId}`);
}

export async function listMembers(
  orgId: string,
): Promise<MembershipResponse[]> {
  const res = await client.get<MembershipResponse[]>(
    `/organizations/${orgId}/members`,
  );
  return res.data;
}

export async function updateMemberRole(
  orgId: string,
  userId: string,
  data: UpdateMemberRoleRequest,
): Promise<MembershipResponse> {
  const res = await client.patch<MembershipResponse>(
    `/organizations/${orgId}/members/${userId}`,
    data,
  );
  return res.data;
}

export async function removeMember(
  orgId: string,
  userId: string,
): Promise<void> {
  await client.delete(`/organizations/${orgId}/members/${userId}`);
}

export async function createInvitation(
  orgId: string,
  data: CreateInvitationRequest,
): Promise<InvitationResponse> {
  const res = await client.post<InvitationResponse>(
    `/organizations/${orgId}/invitations`,
    data,
  );
  return res.data;
}

export async function listInvitations(
  orgId: string,
): Promise<InvitationResponse[]> {
  const res = await client.get<InvitationResponse[]>(
    `/organizations/${orgId}/invitations`,
  );
  return res.data;
}

export async function revokeInvitation(
  orgId: string,
  invitationId: string,
): Promise<void> {
  await client.delete(`/organizations/${orgId}/invitations/${invitationId}`);
}
