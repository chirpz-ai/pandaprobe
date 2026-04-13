import { client } from "@/lib/api/client";
import {
  createOrganization,
  listOrganizations,
  getOrganization,
  updateOrganization,
  deleteOrganization,
  listMembers,
  addMember,
  updateMemberRole,
  removeMember,
} from "@/lib/api/organizations";

jest.mock("axios", () => {
  const mockAxios: Record<string, unknown> = {
    get: jest.fn(),
    post: jest.fn(),
    patch: jest.fn(),
    delete: jest.fn(),
    interceptors: {
      request: { use: jest.fn() },
      response: { use: jest.fn() },
    },
  };
  mockAxios.create = jest.fn(() => mockAxios);
  return { ...mockAxios, default: mockAxios };
});

const mockClient = client as unknown as {
  get: jest.Mock;
  post: jest.Mock;
  patch: jest.Mock;
  delete: jest.Mock;
};

describe("organizations API", () => {
  beforeEach(() => jest.clearAllMocks());

  it("createOrganization posts to /organizations", async () => {
    mockClient.post.mockResolvedValue({ data: { id: "o1", name: "Org" } });
    const result = await createOrganization({ name: "Org" });
    expect(mockClient.post).toHaveBeenCalledWith("/organizations", {
      name: "Org",
    });
    expect(result.name).toBe("Org");
  });

  it("listOrganizations gets /organizations", async () => {
    mockClient.get.mockResolvedValue({ data: [] });
    await listOrganizations();
    expect(mockClient.get).toHaveBeenCalledWith("/organizations");
  });

  it("getOrganization gets /organizations/:id", async () => {
    mockClient.get.mockResolvedValue({ data: { id: "o1" } });
    await getOrganization("o1");
    expect(mockClient.get).toHaveBeenCalledWith("/organizations/o1");
  });

  it("updateOrganization patches /organizations/:id", async () => {
    mockClient.patch.mockResolvedValue({ data: { id: "o1" } });
    await updateOrganization("o1", { name: "Updated" });
    expect(mockClient.patch).toHaveBeenCalledWith("/organizations/o1", {
      name: "Updated",
    });
  });

  it("deleteOrganization deletes /organizations/:id", async () => {
    mockClient.delete.mockResolvedValue({});
    await deleteOrganization("o1");
    expect(mockClient.delete).toHaveBeenCalledWith("/organizations/o1");
  });

  it("listMembers gets /organizations/:id/members", async () => {
    mockClient.get.mockResolvedValue({ data: [] });
    await listMembers("o1");
    expect(mockClient.get).toHaveBeenCalledWith("/organizations/o1/members");
  });

  it("addMember posts to /organizations/:id/members", async () => {
    mockClient.post.mockResolvedValue({ data: { id: "m1" } });
    await addMember("o1", { user_id: "u1", role: "MEMBER" });
    expect(mockClient.post).toHaveBeenCalledWith("/organizations/o1/members", {
      user_id: "u1",
      role: "MEMBER",
    });
  });

  it("updateMemberRole patches /organizations/:id/members/:userId", async () => {
    mockClient.patch.mockResolvedValue({ data: { id: "m1" } });
    await updateMemberRole("o1", "u1", { role: "ADMIN" });
    expect(mockClient.patch).toHaveBeenCalledWith(
      "/organizations/o1/members/u1",
      {
        role: "ADMIN",
      },
    );
  });

  it("removeMember deletes /organizations/:id/members/:userId", async () => {
    mockClient.delete.mockResolvedValue({});
    await removeMember("o1", "u1");
    expect(mockClient.delete).toHaveBeenCalledWith(
      "/organizations/o1/members/u1",
    );
  });
});
