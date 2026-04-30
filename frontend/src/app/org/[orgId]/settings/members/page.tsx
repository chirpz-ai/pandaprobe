"use client";

import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { queryKeys } from "@/lib/query/keys";
import { useOrganization } from "@/components/providers/OrganizationProvider";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";
import {
  listMembers,
  updateMemberRole,
  removeMember,
  createInvitation,
  listInvitations,
  revokeInvitation,
} from "@/lib/api/organizations";
import { extractErrorMessage } from "@/lib/api/client";
import type { MembershipResponse, InvitationResponse } from "@/lib/api/types";
import { MembershipRole, InvitationStatus } from "@/lib/api/enums";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Badge } from "@/components/ui/Badge";
import { LoadingState } from "@/components/common/LoadingState";
import { ErrorState } from "@/components/common/ErrorState";
import { EmptyState } from "@/components/common/EmptyState";
import { ConfirmDialog } from "@/components/common/ConfirmDialog";
import { useToast } from "@/components/providers/ToastProvider";
import {
  Select,
  SelectTrigger,
  SelectContent,
  SelectItem,
  SelectValue,
} from "@/components/ui/Select";
import { Trash2, Mail } from "lucide-react";

const roleVariant: Record<string, "primary" | "info" | "default"> = {
  OWNER: "primary",
  ADMIN: "info",
  MEMBER: "default",
};

const statusVariant: Record<string, "primary" | "info" | "default"> = {
  PENDING: "info",
  ACCEPTED: "primary",
  DECLINED: "default",
  REVOKED: "default",
  EXPIRED: "default",
};

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

export default function MembersPage() {
  const { currentOrg } = useOrganization();
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const orgId = currentOrg?.id ?? "";

  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteRole, setInviteRole] = useState<string>(MembershipRole.MEMBER);
  const [inviting, setInviting] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<MembershipResponse | null>(
    null,
  );
  const [revokeTarget, setRevokeTarget] = useState<InvitationResponse | null>(
    null,
  );

  useDocumentTitle("Members");

  const isAdmin =
    currentOrg?.role === MembershipRole.ADMIN ||
    currentOrg?.role === MembershipRole.OWNER;
  const isOwner = currentOrg?.role === MembershipRole.OWNER;

  const {
    data: members = [],
    isPending,
    error,
    refetch,
  } = useQuery({
    queryKey: queryKeys.members.list(orgId),
    queryFn: () => listMembers(orgId),
    enabled: !!currentOrg,
  });

  const { data: invitations = [] } = useQuery({
    queryKey: queryKeys.invitations.list(orgId),
    queryFn: () => listInvitations(orgId),
    enabled: !!currentOrg,
  });

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: queryKeys.members.list(orgId) });
    queryClient.invalidateQueries({
      queryKey: queryKeys.invitations.list(orgId),
    });
  };

  async function handleInvite() {
    if (!currentOrg || !inviteEmail.trim()) return;
    setInviting(true);
    try {
      await createInvitation(currentOrg.id, {
        email: inviteEmail.trim(),
        role: inviteRole as MembershipResponse["role"],
      });
      toast({ title: "Invitation sent", variant: "success" });
      setInviteEmail("");
      invalidate();
    } catch (err) {
      toast({ title: extractErrorMessage(err), variant: "error" });
    } finally {
      setInviting(false);
    }
  }

  async function handleRoleChange(userId: string, role: string) {
    if (!currentOrg) return;
    try {
      await updateMemberRole(currentOrg.id, userId, {
        role: role as MembershipResponse["role"],
      });
      toast({ title: "Role updated", variant: "success" });
      invalidate();
    } catch (err) {
      toast({ title: extractErrorMessage(err), variant: "error" });
    }
  }

  async function handleRemove() {
    if (!currentOrg || !deleteTarget) return;
    try {
      await removeMember(currentOrg.id, deleteTarget.user_id);
      toast({ title: "Member removed", variant: "success" });
      setDeleteTarget(null);
      invalidate();
    } catch (err) {
      toast({ title: extractErrorMessage(err), variant: "error" });
    }
  }

  async function handleRevoke() {
    if (!currentOrg || !revokeTarget) return;
    try {
      await revokeInvitation(currentOrg.id, revokeTarget.id);
      toast({ title: "Invitation revoked", variant: "success" });
      setRevokeTarget(null);
      invalidate();
    } catch (err) {
      toast({ title: extractErrorMessage(err), variant: "error" });
    }
  }

  if (!currentOrg) return <EmptyState title="No organization selected" />;

  const availableRoles = isOwner
    ? [MembershipRole.MEMBER, MembershipRole.ADMIN]
    : [MembershipRole.MEMBER];

  return (
    <div className="space-y-6 animate-fade-in">
      <h1 className="text-lg font-mono text-primary">Members</h1>

      {isAdmin && (
        <div className="border-engraved bg-surface p-4">
          <div className="flex items-end gap-3 mb-4">
            <div className="ph-no-capture flex-1">
              <label className="text-xs font-mono text-text-muted block mb-1">
                Invite your team
              </label>
              <Input
                type="email"
                value={inviteEmail}
                onChange={(e) => setInviteEmail(e.target.value)}
                placeholder="Email address"
                onKeyDown={(e) => {
                  if (e.key === "Enter" && inviteEmail.trim()) handleInvite();
                }}
              />
            </div>
            <Select value={inviteRole} onValueChange={setInviteRole}>
              <SelectTrigger className="w-32">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {availableRoles.map((r) => (
                  <SelectItem key={r} value={r}>
                    {r}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Button
              size="sm"
              onClick={handleInvite}
              disabled={!inviteEmail.trim() || inviting}
            >
              <Mail className="h-3 w-3" /> Invite
            </Button>
          </div>
        </div>
      )}

      <h2 className="text-sm font-mono text-text-muted">Members</h2>
      {isPending ? (
        <LoadingState />
      ) : error ? (
        <ErrorState
          message={extractErrorMessage(error)}
          onRetry={() => refetch()}
        />
      ) : members.length === 0 ? (
        <EmptyState title="No members" />
      ) : (
        <div className="border border-border overflow-x-auto">
          <table className="w-full text-xs font-mono">
            <thead>
              <tr className="border-b border-border bg-surface-hi">
                <th className="text-left px-3 py-2 text-text-muted font-normal">
                  Name
                </th>
                <th className="text-left px-3 py-2 text-text-muted font-normal">
                  Email
                </th>
                <th className="text-left px-3 py-2 text-text-muted font-normal">
                  Role
                </th>
                <th className="text-left px-3 py-2 text-text-muted font-normal">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody>
              {members.map((m) => (
                <tr
                  key={m.id}
                  className="border-b border-border hover:bg-surface-hi"
                >
                  <td className="ph-no-capture px-3 py-2 text-text">{m.display_name}</td>
                  <td className="ph-no-capture px-3 py-2 text-text-dim">{m.email}</td>
                  <td className="px-3 py-2">
                    {m.role === MembershipRole.OWNER || !isOwner ? (
                      <Badge variant={roleVariant[m.role]}>{m.role}</Badge>
                    ) : (
                      <Select
                        value={m.role}
                        onValueChange={(r) => handleRoleChange(m.user_id, r)}
                      >
                        <SelectTrigger className="w-28 h-7">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          {Object.values(MembershipRole)
                            .filter((r) => r !== MembershipRole.OWNER)
                            .map((r) => (
                              <SelectItem key={r} value={r}>
                                {r}
                              </SelectItem>
                            ))}
                        </SelectContent>
                      </Select>
                    )}
                  </td>
                  <td className="px-3 py-2">
                    {m.role !== MembershipRole.OWNER && isAdmin && (
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => setDeleteTarget(m)}
                      >
                        <Trash2 className="h-3 w-3 text-error" />
                      </Button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div className="space-y-2">
        <h2 className="text-sm font-mono text-text-muted">Invitations</h2>
        {invitations.length === 0 ? (
          <EmptyState title="No invitations" />
        ) : (
          <div className="border border-border overflow-x-auto">
            <table className="w-full text-xs font-mono">
              <thead>
                <tr className="border-b border-border bg-surface-hi">
                  <th className="text-left px-3 py-2 text-text-muted font-normal">
                    Email
                  </th>
                  <th className="text-left px-3 py-2 text-text-muted font-normal">
                    Role
                  </th>
                  <th className="text-left px-3 py-2 text-text-muted font-normal">
                    Status
                  </th>
                  <th className="text-left px-3 py-2 text-text-muted font-normal">
                    Invited By
                  </th>
                  <th className="text-left px-3 py-2 text-text-muted font-normal">
                    Expires
                  </th>
                  {isAdmin && (
                    <th className="text-left px-3 py-2 text-text-muted font-normal">
                      Actions
                    </th>
                  )}
                </tr>
              </thead>
              <tbody>
                {invitations.map((inv) => (
                  <tr
                    key={inv.id}
                    className="border-b border-border hover:bg-surface-hi"
                  >
                    <td className="ph-no-capture px-3 py-2 text-text">{inv.email}</td>
                    <td className="px-3 py-2">
                      <Badge variant={roleVariant[inv.role]}>{inv.role}</Badge>
                    </td>
                    <td className="px-3 py-2">
                      <Badge variant={statusVariant[inv.status]}>
                        {inv.status}
                      </Badge>
                    </td>
                    <td className="ph-no-capture px-3 py-2 text-text-dim">
                      {inv.inviter_display_name || inv.inviter_email}
                    </td>
                    <td className="px-3 py-2 text-text-dim">
                      {formatDate(inv.expires_at)}
                    </td>
                    {isAdmin && (
                      <td className="px-3 py-2">
                        {inv.status === InvitationStatus.PENDING && (
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => setRevokeTarget(inv)}
                          >
                            <Trash2 className="h-3 w-3 text-error" />
                          </Button>
                        )}
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <ConfirmDialog
        open={!!deleteTarget}
        onOpenChange={(open) => !open && setDeleteTarget(null)}
        title="Remove member"
        description={`Remove ${deleteTarget?.display_name ?? "this member"} from the organization?`}
        confirmLabel="Remove"
        onConfirm={handleRemove}
        destructive
      />

      <ConfirmDialog
        open={!!revokeTarget}
        onOpenChange={(open) => !open && setRevokeTarget(null)}
        title="Revoke invitation"
        description={`Revoke the invitation for ${revokeTarget?.email ?? "this user"}?`}
        confirmLabel="Revoke"
        onConfirm={handleRevoke}
        destructive
      />
    </div>
  );
}
