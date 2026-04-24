"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { queryKeys } from "@/lib/query/keys";
import { listMyInvitations, acceptInvitation, declineInvitation } from "@/lib/api/user";
import { extractErrorMessage } from "@/lib/api/client";
import { useToast } from "@/components/providers/ToastProvider";
import { useAuth } from "@/components/providers/AuthProvider";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { Check, X } from "lucide-react";
import { useState } from "react";

export function InvitationBanner() {
  const { toast } = useToast();
  const { user, authEnabled } = useAuth();
  const queryClient = useQueryClient();
  const [processing, setProcessing] = useState<string | null>(null);

  const enabled = authEnabled ? !!user : true;

  const { data: invitations = [] } = useQuery({
    queryKey: queryKeys.invitations.my,
    queryFn: listMyInvitations,
    enabled,
    refetchInterval: 60_000,
  });

  if (invitations.length === 0) return null;

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
    <div className="space-y-2 mb-4">
      {invitations.map((inv) => (
        <div
          key={inv.id}
          className="flex items-center justify-between gap-4 border border-border bg-surface p-3 text-xs font-mono"
        >
          <div className="flex items-center gap-3 min-w-0">
            <Badge variant="info">Invitation</Badge>
            <span className="text-text truncate">
              <strong>{inv.inviter_display_name || inv.inviter_email}</strong>
              {" invited you to join "}
              <strong>{inv.org_name}</strong>
              {" as "}
              <Badge variant="default">{inv.role}</Badge>
            </span>
          </div>
          <div className="flex items-center gap-2 shrink-0">
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
        </div>
      ))}
    </div>
  );
}
