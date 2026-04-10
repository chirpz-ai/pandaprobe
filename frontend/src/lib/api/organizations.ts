import { client } from "./client";
import type {
  CreateOrganizationRequest,
  UpdateOrganizationRequest,
  OrganizationResponse,
  MyOrganizationResponse,
  MembershipResponse,
  AddMemberRequest,
  UpdateMemberRoleRequest,
} from "./types";

export async function createOrganization(
  data: CreateOrganizationRequest
): Promise<OrganizationResponse> {
  const res = await client.post<OrganizationResponse>("/organizations", data);
  return res.data;
}

export async function listOrganizations(): Promise<MyOrganizationResponse[]> {
  const res = await client.get<MyOrganizationResponse[]>("/organizations");
  return res.data;
}

export async function getOrganization(
  orgId: string
): Promise<OrganizationResponse> {
  const res = await client.get<OrganizationResponse>(
    `/organizations/${orgId}`
  );
  return res.data;
}

export async function updateOrganization(
  orgId: string,
  data: UpdateOrganizationRequest
): Promise<OrganizationResponse> {
  const res = await client.patch<OrganizationResponse>(
    `/organizations/${orgId}`,
    data
  );
  return res.data;
}

export async function deleteOrganization(orgId: string): Promise<void> {
  await client.delete(`/organizations/${orgId}`);
}

export async function listMembers(
  orgId: string
): Promise<MembershipResponse[]> {
  const res = await client.get<MembershipResponse[]>(
    `/organizations/${orgId}/members`
  );
  return res.data;
}

export async function addMember(
  orgId: string,
  data: AddMemberRequest
): Promise<MembershipResponse> {
  const res = await client.post<MembershipResponse>(
    `/organizations/${orgId}/members`,
    data
  );
  return res.data;
}

export async function updateMemberRole(
  orgId: string,
  userId: string,
  data: UpdateMemberRoleRequest
): Promise<MembershipResponse> {
  const res = await client.patch<MembershipResponse>(
    `/organizations/${orgId}/members/${userId}`,
    data
  );
  return res.data;
}

export async function removeMember(
  orgId: string,
  userId: string
): Promise<void> {
  await client.delete(`/organizations/${orgId}/members/${userId}`);
}
