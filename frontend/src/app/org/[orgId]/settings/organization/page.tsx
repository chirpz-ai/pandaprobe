"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { AlertTriangle, Copy, Check, Save, Loader2 } from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";
import { useOrganization } from "@/components/providers/OrganizationProvider";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";
import {
  updateOrganization,
  deleteOrganization,
} from "@/lib/api/organizations";
import { extractErrorMessage } from "@/lib/api/client";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Badge } from "@/components/ui/Badge";
import { LoadingState } from "@/components/common/LoadingState";
import { FormDialog } from "@/components/common/FormDialog";
import { useToast } from "@/components/providers/ToastProvider";
import { queryKeys } from "@/lib/query/keys";
import { STORAGE_KEYS } from "@/lib/utils/constants";

const ROLE_BADGE_VARIANT = {
  OWNER: "primary",
  ADMIN: "info",
  MEMBER: "default",
} as const;

export default function OrganizationSettingsPage() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const {
    currentOrg,
    organizations,
    refetchOrgs: refetch,
    loading,
  } = useOrganization();
  const { toast } = useToast();
  const [name, setName] = useState(currentOrg?.name ?? "");
  const [saving, setSaving] = useState(false);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (currentOrg?.name != null) {
      setName(currentOrg.name);
    }
  }, [currentOrg?.name]);

  useDocumentTitle("Organization Settings");

  if (loading) return <LoadingState />;
  if (!currentOrg)
    return (
      <div className="text-text-dim text-sm">No organization selected</div>
    );

  const isOwner = currentOrg.role === "OWNER";
  const canEdit = currentOrg.role !== "MEMBER";

  async function handleCopyId() {
    if (!currentOrg) return;
    await navigator.clipboard.writeText(currentOrg.id);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  async function handleSave() {
    if (!currentOrg || !name.trim()) return;
    setSaving(true);
    try {
      await updateOrganization(currentOrg.id, { name: name.trim() });
      toast({ title: "Organization updated", variant: "success" });
      await refetch();
    } catch (err) {
      toast({ title: extractErrorMessage(err), variant: "error" });
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete() {
    if (!currentOrg) return;
    const nextOrg = organizations.find((o) => o.id !== currentOrg.id);
    await deleteOrganization(currentOrg.id);

    // Clear the org query cache entirely instead of refetching.
    queryClient.removeQueries({ queryKey: queryKeys.organizations.all });
    queryClient.removeQueries({
      queryKey: queryKeys.projects.all(currentOrg.id),
    });

    localStorage.removeItem(STORAGE_KEYS.orgId);
    if (nextOrg) {
      localStorage.setItem(STORAGE_KEYS.orgId, nextOrg.id);
      router.replace(`/org/${nextOrg.id}/settings/organization`);
    } else {
      router.replace("/");
    }
  }

  return (
    <div className="space-y-6 animate-fade-in">
      <h1 className="text-lg font-mono text-primary">Organization</h1>

      {/* ── General Info ──────────────────────────────────────────── */}
      <div className="border-engraved bg-surface p-4 space-y-4">
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <div>
            <label className="text-xs font-mono text-text-muted block mb-1">
              Organization ID
            </label>
            <div className="flex items-center gap-2">
              <span className="ph-no-capture text-xs font-mono text-text-dim truncate">
                {currentOrg.id}
              </span>
              <button
                onClick={handleCopyId}
                className="flex-shrink-0 text-text-muted hover:text-text transition-colors"
                title="Copy ID"
              >
                {copied ? (
                  <Check className="h-3.5 w-3.5 text-success" />
                ) : (
                  <Copy className="h-3.5 w-3.5" />
                )}
              </button>
            </div>
          </div>
          <div>
            <label className="text-xs font-mono text-text-muted block mb-1">
              Role
            </label>
            <Badge variant={ROLE_BADGE_VARIANT[currentOrg.role]}>
              {currentOrg.role}
            </Badge>
          </div>
          <div>
            <label className="text-xs font-mono text-text-muted block mb-1">
              Created
            </label>
            <span className="text-xs font-mono text-text-dim">
              {new Date(currentOrg.created_at).toLocaleDateString(undefined, {
                year: "numeric",
                month: "long",
                day: "numeric",
              })}
            </span>
          </div>
        </div>
        <div className="flex items-end gap-3">
          <div className="flex-1">
            <label className="text-xs font-mono text-text-muted block mb-1">
              Name
            </label>
            <Input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Organization name"
              disabled={!canEdit}
            />
          </div>
          {canEdit && (
            <Button
              size="sm"
              onClick={handleSave}
              disabled={
                saving || !name.trim() || name.trim() === currentOrg.name
              }
            >
              {saving ? (
                <Loader2 className="h-3 w-3 animate-spin" />
              ) : (
                <Save className="h-3 w-3" />
              )}{" "}
              {saving ? "Saving..." : "Save"}
            </Button>
          )}
        </div>
      </div>

      {/* ── Danger Zone ───────────────────────────────────────────── */}
      <DeleteOrganizationSection
        orgName={currentOrg.name}
        onDelete={handleDelete}
        disabled={!isOwner}
      />
    </div>
  );
}

function DeleteOrganizationSection({
  orgName,
  onDelete,
  disabled,
}: {
  orgName: string;
  onDelete: () => Promise<void>;
  disabled: boolean;
}) {
  const { toast } = useToast();
  const [open, setOpen] = useState(false);
  const [confirmation, setConfirmation] = useState("");

  const confirmed = confirmation === orgName;

  async function handleDelete() {
    if (!confirmed) return;
    try {
      await onDelete();
      toast({ title: "Organization deleted", variant: "success" });
    } catch (err) {
      toast({ title: extractErrorMessage(err), variant: "error" });
      throw err;
    }
  }

  return (
    <div
      className={
        disabled
          ? "border border-border bg-surface p-4 space-y-3 opacity-60"
          : "border border-error/30 bg-error/5 p-4 space-y-3"
      }
    >
      <div className="flex items-center gap-2">
        <AlertTriangle
          className={
            disabled ? "h-4 w-4 text-text-muted" : "h-4 w-4 text-error"
          }
        />
        <h2
          className={
            disabled
              ? "text-sm font-mono text-text-muted"
              : "text-sm font-mono text-error"
          }
        >
          Danger Zone
        </h2>
      </div>
      <p className="text-xs font-mono text-text-dim">
        {disabled
          ? "Only the organization owner can delete this organization."
          : "Deleting this organization is permanent. All projects, traces, evaluations, API keys, and member data will be irreversibly removed."}
      </p>

      <Button
        variant="destructive"
        size="sm"
        disabled={disabled}
        onClick={() => setOpen(true)}
      >
        Delete Organization
      </Button>

      <FormDialog
        open={open}
        onOpenChange={(v) => {
          setOpen(v);
          if (!v) setConfirmation("");
        }}
        variant="destructive"
        title="Delete Organization"
        titleIcon={<AlertTriangle className="h-4 w-4" />}
        description={
          <>
            This action is <strong className="text-error">permanent</strong> and
            cannot be undone. All projects, traces, evaluations, API keys, and
            member associations will be deleted.
          </>
        }
        submitLabel="I understand, delete this organization"
        submitDisabled={!confirmed}
        onSubmit={handleDelete}
      >
        <div>
          <label className="text-xs font-mono text-text-muted block mb-1">
            Type <span className="text-text font-semibold">{orgName}</span> to
            confirm
          </label>
          <Input
            value={confirmation}
            onChange={(e) => setConfirmation(e.target.value)}
            placeholder={orgName}
            autoFocus
          />
        </div>
      </FormDialog>
    </div>
  );
}
