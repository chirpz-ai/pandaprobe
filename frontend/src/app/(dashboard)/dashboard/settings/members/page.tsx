"use client";

import { useEffect, useState, useCallback } from "react";
import { useOrganization } from "@/components/providers/OrganizationProvider";
import {
  listMembers,
  addMember,
  updateMemberRole,
  removeMember,
} from "@/lib/api/organizations";
import type { MembershipResponse } from "@/lib/api/types";
import { MembershipRole } from "@/lib/api/enums";
import { Button } from "@/components/atoms/Button";
import { Input } from "@/components/atoms/Input";
import { Badge } from "@/components/atoms/Badge";
import { LoadingState } from "@/components/molecules/LoadingState";
import { ErrorState } from "@/components/molecules/ErrorState";
import { EmptyState } from "@/components/molecules/EmptyState";
import { ConfirmDialog } from "@/components/molecules/ConfirmDialog";
import { useToast } from "@/components/providers/ToastProvider";
import {
  Select,
  SelectTrigger,
  SelectContent,
  SelectItem,
  SelectValue,
} from "@/components/atoms/Select";
import { Trash2, UserPlus } from "lucide-react";

const roleVariant: Record<string, "primary" | "info" | "default"> = {
  OWNER: "primary",
  ADMIN: "info",
  MEMBER: "default",
};

export default function MembersPage() {
  const { currentOrg } = useOrganization();
  const { toast } = useToast();

  const [members, setMembers] = useState<MembershipResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [newUserId, setNewUserId] = useState("");
  const [newRole, setNewRole] = useState<string>(MembershipRole.MEMBER);
  const [deleteTarget, setDeleteTarget] = useState<MembershipResponse | null>(null);

  const fetchData = useCallback(async () => {
    if (!currentOrg) return;
    setLoading(true);
    setError(null);
    try {
      const result = await listMembers(currentOrg.id);
      setMembers(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load members");
    } finally {
      setLoading(false);
    }
  }, [currentOrg]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  async function handleAdd() {
    if (!currentOrg || !newUserId.trim()) return;
    try {
      await addMember(currentOrg.id, {
        user_id: newUserId.trim(),
        role: newRole as MembershipResponse["role"],
      });
      toast({ title: "Member added", variant: "success" });
      setNewUserId("");
      fetchData();
    } catch {
      toast({ title: "Failed to add member", variant: "error" });
    }
  }

  async function handleRoleChange(userId: string, role: string) {
    if (!currentOrg) return;
    try {
      await updateMemberRole(currentOrg.id, userId, {
        role: role as MembershipResponse["role"],
      });
      toast({ title: "Role updated", variant: "success" });
      fetchData();
    } catch {
      toast({ title: "Failed to update role", variant: "error" });
    }
  }

  async function handleRemove() {
    if (!currentOrg || !deleteTarget) return;
    try {
      await removeMember(currentOrg.id, deleteTarget.user_id);
      toast({ title: "Member removed", variant: "success" });
      setDeleteTarget(null);
      fetchData();
    } catch {
      toast({ title: "Failed to remove member", variant: "error" });
    }
  }

  if (!currentOrg) return <EmptyState title="No organization selected" />;

  return (
    <div className="space-y-6 animate-fade-in">
      <h1 className="text-lg font-mono text-primary">Members</h1>

      <div className="border-engraved bg-surface p-4">
        <div className="flex items-end gap-3 mb-4">
          <div className="flex-1">
            <label className="text-xs font-mono text-text-muted block mb-1">User ID</label>
            <Input
              value={newUserId}
              onChange={(e) => setNewUserId(e.target.value)}
              placeholder="User UUID"
            />
          </div>
          <Select value={newRole} onValueChange={setNewRole}>
            <SelectTrigger className="w-32">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {Object.values(MembershipRole).map((r) => (
                <SelectItem key={r} value={r}>{r}</SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Button size="sm" onClick={handleAdd} disabled={!newUserId.trim()}>
            <UserPlus className="h-3 w-3" /> Add
          </Button>
        </div>
      </div>

      {loading ? (
        <LoadingState />
      ) : error ? (
        <ErrorState message={error} onRetry={fetchData} />
      ) : members.length === 0 ? (
        <EmptyState title="No members" />
      ) : (
        <div className="border border-border overflow-x-auto">
          <table className="w-full text-xs font-mono">
            <thead>
              <tr className="border-b border-border bg-surface-hi">
                <th className="text-left px-3 py-2 text-text-muted font-normal">Name</th>
                <th className="text-left px-3 py-2 text-text-muted font-normal">Email</th>
                <th className="text-left px-3 py-2 text-text-muted font-normal">Role</th>
                <th className="text-left px-3 py-2 text-text-muted font-normal">Actions</th>
              </tr>
            </thead>
            <tbody>
              {members.map((m) => (
                <tr key={m.id} className="border-b border-border hover:bg-surface-hi">
                  <td className="px-3 py-2 text-text">{m.display_name}</td>
                  <td className="px-3 py-2 text-text-dim">{m.email}</td>
                  <td className="px-3 py-2">
                    {m.role === MembershipRole.OWNER ? (
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
                          {Object.values(MembershipRole).filter(r => r !== MembershipRole.OWNER).map((r) => (
                            <SelectItem key={r} value={r}>{r}</SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    )}
                  </td>
                  <td className="px-3 py-2">
                    {m.role !== MembershipRole.OWNER && (
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

      <ConfirmDialog
        open={!!deleteTarget}
        onOpenChange={(open) => !open && setDeleteTarget(null)}
        title="Remove member"
        description={`Remove ${deleteTarget?.display_name ?? "this member"} from the organization?`}
        confirmLabel="Remove"
        onConfirm={handleRemove}
        destructive
      />
    </div>
  );
}
