"use client";

import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { queryKeys } from "@/lib/query/keys";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";
import {
  listMyInvitations,
  acceptInvitation,
  declineInvitation,
} from "@/lib/api/user";
import { extractErrorMessage } from "@/lib/api/client";
import { useAuth } from "@/components/providers/AuthProvider";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { LoadingState } from "@/components/common/LoadingState";
import { EmptyState } from "@/components/common/EmptyState";
import { useToast } from "@/components/providers/ToastProvider";
import { Check, X } from "lucide-react";

const roleVariant: Record<string, "primary" | "info" | "default"> = {
  OWNER: "primary",
  ADMIN: "info",
  MEMBER: "default",
};

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

export default function InvitationsPage() {
  const { toast } = useToast();
  const { user: authUser, authEnabled } = useAuth();
  const queryClient = useQueryClient();
  const [processing, setProcessing] = useState<string | null>(null);

  useDocumentTitle("Invitations");

  const authReady = authEnabled ? !!authUser : true;

  const { data: invitations = [], isPending } = useQuery({
    queryKey: queryKeys.invitations.my,
    queryFn: listMyInvitations,
    enabled: authReady,
  });

  async function handleAccept(id: string) {
    setProcessing(id);
    try {
      await acceptInvitation(id);
      toast({ title: "Invitation accepted", variant: "success" });
      queryClient.invalidateQueries({ queryKey: queryKeys.invitations.my });
      queryClient.invalidateQueries({ queryKey: queryKeys.organizations.all });
    } catch (err) {
      toast({ title: extractErrorMessage(err), variant: "error" });
    } finally {
      setProcessing(null);
    }
  }

  async function handleDecline(id: string) {
    setProcessing(id);
    try {
      await declineInvitation(id);
      toast({ title: "Invitation declined", variant: "success" });
      queryClient.invalidateQueries({ queryKey: queryKeys.invitations.my });
    } catch (err) {
      toast({ title: extractErrorMessage(err), variant: "error" });
    } finally {
      setProcessing(null);
    }
  }

  return (
    <div className="space-y-6 animate-fade-in">
      <h1 className="text-lg font-mono text-primary">Invitations</h1>

      {isPending ? (
        <LoadingState />
      ) : invitations.length === 0 ? (
        <EmptyState title="No pending invitations" />
      ) : (
        <div className="border border-border overflow-x-auto">
          <table className="w-full text-xs font-mono">
            <thead>
              <tr className="border-b border-border bg-surface-hi">
                <th className="text-left px-3 py-2 text-text-muted font-normal">
                  Organization
                </th>
                <th className="text-left px-3 py-2 text-text-muted font-normal">
                  Role
                </th>
                <th className="text-left px-3 py-2 text-text-muted font-normal">
                  Invited By
                </th>
                <th className="text-left px-3 py-2 text-text-muted font-normal">
                  Expires
                </th>
                <th className="text-left px-3 py-2 text-text-muted font-normal">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody>
              {invitations.map((inv) => (
                <tr
                  key={inv.id}
                  className="border-b border-border hover:bg-surface-hi"
                >
                  <td className="px-3 py-2 text-text font-medium">
                    {inv.org_name}
                  </td>
                  <td className="px-3 py-2">
                    <Badge variant={roleVariant[inv.role]}>{inv.role}</Badge>
                  </td>
                  <td className="px-3 py-2 text-text-dim">
                    {inv.inviter_display_name || inv.inviter_email}
                  </td>
                  <td className="px-3 py-2 text-text-dim">
                    {formatDate(inv.expires_at)}
                  </td>
                  <td className="px-3 py-2">
                    <div className="flex items-center gap-2">
                      <Button
                        size="sm"
                        onClick={() => handleAccept(inv.id)}
                        disabled={processing === inv.id}
                      >
                        <Check className="h-3 w-3" /> Accept
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleDecline(inv.id)}
                        disabled={processing === inv.id}
                      >
                        <X className="h-3 w-3" /> Decline
                      </Button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
