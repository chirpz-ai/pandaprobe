"use client";

import { useState } from "react";
import { useOrganization } from "@/components/providers/OrganizationProvider";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";
import { updateOrganization } from "@/lib/api/organizations";
import { extractErrorMessage } from "@/lib/api/client";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { LoadingState } from "@/components/common/LoadingState";
import { useToast } from "@/components/providers/ToastProvider";

export default function OrganizationSettingsPage() {
  const { currentOrg, refetchOrgs: refetch, loading } = useOrganization();
  const { toast } = useToast();
  const [name, setName] = useState(currentOrg?.name ?? "");
  const [saving, setSaving] = useState(false);

  useDocumentTitle("Organization Settings");

  if (loading) return <LoadingState />;
  if (!currentOrg)
    return (
      <div className="text-text-dim text-sm">No organization selected</div>
    );

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

  return (
    <div className="space-y-6 animate-fade-in max-w-lg">
      <h1 className="text-lg font-mono text-primary">Organization</h1>

      <div className="border-engraved bg-surface p-4 space-y-4">
        <div>
          <label className="text-xs font-mono text-text-muted block mb-1">
            Organization ID
          </label>
          <span className="text-xs font-mono text-text-dim">
            {currentOrg.id}
          </span>
        </div>
        <div>
          <label className="text-xs font-mono text-text-muted block mb-1">
            Name
          </label>
          <Input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Organization name"
          />
        </div>
        <Button onClick={handleSave} disabled={saving || !name.trim()}>
          {saving ? "Saving..." : "Save"}
        </Button>
      </div>
    </div>
  );
}
