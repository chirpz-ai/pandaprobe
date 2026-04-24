"use client";

import { useQuery } from "@tanstack/react-query";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";
import { getProfile } from "@/lib/api/user";
import { useAuth } from "@/components/providers/AuthProvider";
import { LoadingState } from "@/components/common/LoadingState";
import { EmptyState } from "@/components/common/EmptyState";

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

export default function AccountPage() {
  const { user: authUser, authEnabled } = useAuth();

  useDocumentTitle("Account");

  const authReady = authEnabled ? !!authUser : true;

  const { data: profile, isPending } = useQuery({
    queryKey: ["me", "profile"],
    queryFn: getProfile,
    enabled: authReady,
  });

  return (
    <div className="space-y-6 animate-fade-in">
      <h1 className="text-lg font-mono text-primary">Account</h1>

      {isPending ? (
        <LoadingState />
      ) : profile ? (
        <div className="border border-border bg-surface p-4">
          <div className="grid grid-cols-[auto_1fr] gap-x-6 gap-y-2 text-xs font-mono">
            <span className="text-text-muted">Email</span>
            <span className="text-text">{profile.email}</span>
            <span className="text-text-muted">Display Name</span>
            <span className="text-text">{profile.display_name || "—"}</span>
            <span className="text-text-muted">Member Since</span>
            <span className="text-text">{formatDate(profile.created_at)}</span>
          </div>
        </div>
      ) : (
        <EmptyState title="Could not load profile" />
      )}
    </div>
  );
}
