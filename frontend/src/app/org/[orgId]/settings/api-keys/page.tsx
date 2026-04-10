"use client";

import { useEffect, useState, useCallback } from "react";
import { useOrganization } from "@/components/providers/OrganizationProvider";
import {
  listAPIKeys,
  createAPIKey,
  rotateAPIKey,
  deleteAPIKey,
} from "@/lib/api/api-keys";
import type { APIKeyResponse } from "@/lib/api/types";
import { KeyExpiration } from "@/lib/api/enums";
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
import { Plus, RotateCw, Trash2, Copy, Eye, EyeOff } from "lucide-react";
import { formatDateTime } from "@/lib/utils/format";

export default function APIKeysPage() {
  const { currentOrg } = useOrganization();
  const { toast } = useToast();

  const [keys, setKeys] = useState<APIKeyResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [newName, setNewName] = useState("");
  const [expiration, setExpiration] = useState<string>(KeyExpiration.never);
  const [newRawKey, setNewRawKey] = useState<string | null>(null);
  const [showRawKey, setShowRawKey] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<APIKeyResponse | null>(null);

  const fetchData = useCallback(async () => {
    if (!currentOrg) return;
    setLoading(true);
    setError(null);
    try {
      const result = await listAPIKeys(currentOrg.id);
      setKeys(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load API keys");
    } finally {
      setLoading(false);
    }
  }, [currentOrg]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  async function handleCreate() {
    if (!currentOrg || !newName.trim()) return;
    try {
      const result = await createAPIKey(currentOrg.id, {
        name: newName.trim(),
        expiration: expiration as APIKeyResponse["is_active"] extends boolean
          ? typeof expiration extends string
            ? never
            : never
          : never,
      });
      setNewRawKey(result.raw_key);
      setShowRawKey(true);
      toast({ title: "API key created", variant: "success" });
      setNewName("");
      fetchData();
    } catch {
      toast({ title: "Failed to create API key", variant: "error" });
    }
  }

  async function handleRotate(keyId: string) {
    if (!currentOrg) return;
    try {
      const result = await rotateAPIKey(currentOrg.id, keyId);
      setNewRawKey(result.raw_key);
      setShowRawKey(true);
      toast({ title: "API key rotated", variant: "success" });
      fetchData();
    } catch {
      toast({ title: "Failed to rotate API key", variant: "error" });
    }
  }

  async function handleDelete() {
    if (!currentOrg || !deleteTarget) return;
    try {
      await deleteAPIKey(currentOrg.id, deleteTarget.id, false);
      toast({ title: "API key deleted", variant: "success" });
      setDeleteTarget(null);
      fetchData();
    } catch {
      toast({ title: "Failed to delete API key", variant: "error" });
    }
  }

  function copyToClipboard(text: string) {
    navigator.clipboard.writeText(text);
    toast({ title: "Copied to clipboard", variant: "success" });
  }

  if (!currentOrg) return <EmptyState title="No organization selected" />;

  return (
    <div className="space-y-6 animate-fade-in">
      <h1 className="text-lg font-mono text-primary">API Keys</h1>

      <div className="border-engraved bg-surface p-4">
        <div className="flex items-end gap-3 mb-4">
          <div className="flex-1">
            <label className="text-xs font-mono text-text-muted block mb-1">Key Name</label>
            <Input
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              placeholder="e.g. Production"
            />
          </div>
          <Select value={expiration} onValueChange={setExpiration}>
            <SelectTrigger className="w-32">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {Object.values(KeyExpiration).map((e) => (
                <SelectItem key={e} value={e}>{e}</SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Button size="sm" onClick={handleCreate} disabled={!newName.trim()}>
            <Plus className="h-3 w-3" /> Create
          </Button>
        </div>

        {newRawKey && (
          <div className="bg-warning/5 border border-warning/20 p-3 mt-3">
            <p className="text-xs text-warning font-mono mb-2">
              Copy this key now. You won&apos;t be able to see it again.
            </p>
            <div className="flex items-center gap-2">
              <code className="flex-1 text-xs font-mono text-text bg-bg px-2 py-1 border border-border overflow-hidden">
                {showRawKey ? newRawKey : "••••••••••••••••"}
              </code>
              <Button variant="ghost" size="icon" onClick={() => setShowRawKey(!showRawKey)}>
                {showRawKey ? <EyeOff className="h-3 w-3" /> : <Eye className="h-3 w-3" />}
              </Button>
              <Button variant="ghost" size="icon" onClick={() => copyToClipboard(newRawKey)}>
                <Copy className="h-3 w-3" />
              </Button>
            </div>
          </div>
        )}
      </div>

      {loading ? (
        <LoadingState />
      ) : error ? (
        <ErrorState message={error} onRetry={fetchData} />
      ) : keys.length === 0 ? (
        <EmptyState title="No API keys" description="Create an API key to authenticate programmatic access." />
      ) : (
        <div className="border border-border overflow-x-auto">
          <table className="w-full text-xs font-mono">
            <thead>
              <tr className="border-b border-border bg-surface-hi">
                <th className="text-left px-3 py-2 text-text-muted font-normal">Name</th>
                <th className="text-left px-3 py-2 text-text-muted font-normal">Prefix</th>
                <th className="text-left px-3 py-2 text-text-muted font-normal">Status</th>
                <th className="text-left px-3 py-2 text-text-muted font-normal">Expires</th>
                <th className="text-left px-3 py-2 text-text-muted font-normal">Created</th>
                <th className="text-left px-3 py-2 text-text-muted font-normal">Actions</th>
              </tr>
            </thead>
            <tbody>
              {keys.map((key) => (
                <tr key={key.id} className="border-b border-border hover:bg-surface-hi">
                  <td className="px-3 py-2 text-text">{key.name}</td>
                  <td className="px-3 py-2 text-text-dim font-mono">{key.key_prefix}...</td>
                  <td className="px-3 py-2">
                    <Badge variant={key.is_active ? "success" : "error"}>
                      {key.is_active ? "Active" : "Revoked"}
                    </Badge>
                  </td>
                  <td className="px-3 py-2 text-text-dim">
                    {key.expires_at ? formatDateTime(key.expires_at) : "Never"}
                  </td>
                  <td className="px-3 py-2 text-text-dim">{formatDateTime(key.created_at)}</td>
                  <td className="px-3 py-2 flex gap-1">
                    <Button variant="ghost" size="sm" onClick={() => handleRotate(key.id)}>
                      <RotateCw className="h-3 w-3" />
                    </Button>
                    <Button variant="ghost" size="sm" onClick={() => setDeleteTarget(key)}>
                      <Trash2 className="h-3 w-3 text-error" />
                    </Button>
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
        title="Delete API key"
        description={`Delete the API key "${deleteTarget?.name}"? Applications using this key will lose access.`}
        confirmLabel="Delete"
        onConfirm={handleDelete}
        destructive
      />
    </div>
  );
}
