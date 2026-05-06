"use client";

import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { queryKeys } from "@/lib/query/keys";
import { useOrganization } from "@/components/providers/OrganizationProvider";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";
import {
  listAPIKeys,
  createAPIKey,
  rotateAPIKey,
  deleteAPIKey,
} from "@/lib/api/api-keys";
import { extractErrorMessage } from "@/lib/api/client";
import type { APIKeyResponse } from "@/lib/api/types";
import { KeyExpiration } from "@/lib/api/enums";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Badge } from "@/components/ui/Badge";
import { Tooltip } from "@/components/ui/Tooltip";
import { LoadingState } from "@/components/common/LoadingState";
import { ErrorState } from "@/components/common/ErrorState";
import { EmptyState } from "@/components/common/EmptyState";
import { Dialog } from "@/components/common/Dialog";
import { FormDialog } from "@/components/common/FormDialog";
import { useToast } from "@/components/providers/ToastProvider";
import {
  Select,
  SelectTrigger,
  SelectContent,
  SelectItem,
  SelectValue,
} from "@/components/ui/Select";
import {
  Plus,
  RotateCw,
  Trash2,
  Copy,
  Eye,
  EyeOff,
  Check,
  KeyRound,
  Loader2,
  X,
} from "lucide-react";
import { formatDateTime } from "@/lib/utils/format";

export default function APIKeysPage() {
  const { currentOrg } = useOrganization();
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const orgId = currentOrg?.id ?? "";

  const [createOpen, setCreateOpen] = useState(false);
  const [rotatedRawKey, setRotatedRawKey] = useState<string | null>(null);
  const [showRotatedKey, setShowRotatedKey] = useState(false);
  const [rotatedCopied, setRotatedCopied] = useState(false);
  const [rotatedKeySaved, setRotatedKeySaved] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<APIKeyResponse | null>(null);
  const [deleteMode, setDeleteMode] = useState<"revoke" | "permanent">(
    "revoke",
  );

  useDocumentTitle("API Keys");

  const {
    data: keys = [],
    isPending,
    error,
    refetch,
  } = useQuery({
    queryKey: queryKeys.apiKeys.list(orgId),
    queryFn: () => listAPIKeys(orgId),
    enabled: !!currentOrg,
  });

  const invalidate = () =>
    queryClient.invalidateQueries({ queryKey: queryKeys.apiKeys.list(orgId) });

  async function handleRotate(keyId: string) {
    if (!currentOrg) return;
    try {
      const result = await rotateAPIKey(currentOrg.id, keyId);
      setRotatedRawKey(result.raw_key);
      setShowRotatedKey(true);
      setRotatedCopied(false);
      setRotatedKeySaved(false);
      toast({ title: "API key rotated", variant: "success" });
      invalidate();
    } catch (err) {
      toast({ title: extractErrorMessage(err), variant: "error" });
    }
  }

  function copyRotatedKey() {
    if (!rotatedRawKey) return;
    navigator.clipboard.writeText(rotatedRawKey);
    toast({ title: "Copied to clipboard", variant: "success" });
    setRotatedCopied(true);
    setRotatedKeySaved(true);
    setTimeout(() => setRotatedCopied(false), 2000);
  }

  function openDelete(key: APIKeyResponse) {
    setDeleteTarget(key);
    setDeleteMode("revoke");
  }

  async function handleDelete() {
    if (!currentOrg || !deleteTarget) return;
    const permanent = deleteMode === "permanent";
    try {
      await deleteAPIKey(currentOrg.id, deleteTarget.id, permanent);
      toast({
        title: permanent ? "API key permanently deleted" : "API key revoked",
        variant: "success",
      });
      setDeleteTarget(null);
      invalidate();
    } catch (err) {
      toast({ title: extractErrorMessage(err), variant: "error" });
      throw err;
    }
  }

  if (!currentOrg) return <EmptyState title="No organization selected" />;

  const canManage = currentOrg.role !== "MEMBER";

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-mono text-primary">API Keys</h1>
        <Button size="sm" onClick={() => setCreateOpen(true)}>
          <Plus className="h-3 w-3" /> Create new API key
        </Button>
      </div>

      <CreateKeyDialog
        open={createOpen}
        onOpenChange={setCreateOpen}
        orgId={orgId}
        onCreated={invalidate}
      />

      {rotatedRawKey && (
        <div className="bg-warning/5 border border-warning/20 p-3 space-y-3">
          <div className="flex items-center justify-between">
            <p className="text-xs text-warning font-mono">
              Copy this rotated key now. You won&apos;t be able to see it again.
            </p>
            <Tooltip
              content={rotatedKeySaved ? "" : "Copy the key before dismissing"}
            >
              <span>
                <Button
                  size="sm"
                  disabled={!rotatedKeySaved}
                  onClick={() => {
                    setRotatedRawKey(null);
                    setRotatedKeySaved(false);
                  }}
                >
                  Done
                </Button>
              </span>
            </Tooltip>
          </div>
          <div className="flex items-center gap-2">
            <code className="ph-no-capture flex-1 text-xs font-mono text-text bg-bg px-2 py-2 border border-border overflow-x-auto whitespace-nowrap scrollbar-hide">
              {showRotatedKey ? rotatedRawKey : "••••••••••••••••"}
            </code>
            <Tooltip content="Toggle visibility">
              <Button
                variant="ghost"
                size="icon"
                onClick={() => setShowRotatedKey(!showRotatedKey)}
              >
                {showRotatedKey ? (
                  <EyeOff className="h-3 w-3" />
                ) : (
                  <Eye className="h-3 w-3" />
                )}
              </Button>
            </Tooltip>
            <Tooltip content={rotatedCopied ? "Copied!" : "Copy"}>
              <Button variant="ghost" size="icon" onClick={copyRotatedKey}>
                {rotatedCopied ? (
                  <Check className="h-3 w-3 text-success" />
                ) : (
                  <Copy className="h-3 w-3" />
                )}
              </Button>
            </Tooltip>
          </div>
        </div>
      )}

      {isPending ? (
        <LoadingState />
      ) : error ? (
        <ErrorState
          message={extractErrorMessage(error)}
          onRetry={() => refetch()}
        />
      ) : keys.length === 0 ? (
        <EmptyState
          title="No API keys"
          description="Create an API key to authenticate programmatic access."
        />
      ) : (
        <div className="border border-border overflow-x-auto">
          <table className="w-full text-xs font-mono">
            <thead>
              <tr className="border-b border-border bg-surface-hi">
                <th className="text-left px-3 py-2 text-text-muted font-normal">
                  Name
                </th>
                <th className="text-left px-3 py-2 text-text-muted font-normal">
                  Prefix
                </th>
                <th className="text-left px-3 py-2 text-text-muted font-normal">
                  Status
                </th>
                <th className="text-left px-3 py-2 text-text-muted font-normal">
                  Expires
                </th>
                <th className="text-left px-3 py-2 text-text-muted font-normal">
                  Created
                </th>
                <th className="text-left px-3 py-2 text-text-muted font-normal">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody>
              {keys.map((key) => (
                <tr
                  key={key.id}
                  className="border-b border-border hover:bg-surface-hi"
                >
                  <td className="px-3 py-2 text-text">{key.name}</td>
                  <td className="ph-no-capture px-3 py-2 text-text-dim font-mono">
                    {key.key_prefix}...
                  </td>
                  <td className="px-3 py-2">
                    <Badge variant={key.is_active ? "success" : "error"}>
                      {key.is_active ? "Active" : "Revoked"}
                    </Badge>
                  </td>
                  <td className="px-3 py-2 text-text-dim">
                    {key.expires_at ? formatDateTime(key.expires_at) : "Never"}
                  </td>
                  <td className="px-3 py-2 text-text-dim">
                    {formatDateTime(key.created_at)}
                  </td>
                  <td className="px-3 py-2">
                    <div className="flex items-center gap-1">
                      <Tooltip
                        content={
                          canManage
                            ? "Rotate"
                            : "Only owner and admins can rotate keys"
                        }
                      >
                        <span tabIndex={canManage ? undefined : 0}>
                          <Button
                            variant="ghost"
                            size="sm"
                            disabled={!canManage}
                            onClick={() => handleRotate(key.id)}
                          >
                            <RotateCw className="h-3 w-3" />
                          </Button>
                        </span>
                      </Tooltip>
                      <Tooltip
                        content={
                          canManage
                            ? "Revoke / Delete"
                            : "Only owner and admins can revoke keys"
                        }
                      >
                        <span tabIndex={canManage ? undefined : 0}>
                          <Button
                            variant="ghost"
                            size="sm"
                            disabled={!canManage}
                            onClick={() => openDelete(key)}
                          >
                            <Trash2 className="h-3 w-3 text-error" />
                          </Button>
                        </span>
                      </Tooltip>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <FormDialog
        open={!!deleteTarget}
        onOpenChange={(v) => {
          if (!v) setDeleteTarget(null);
        }}
        variant="destructive"
        title="Remove API Key"
        titleIcon={<Trash2 className="h-4 w-4" />}
        description={
          <>
            You are about to remove the API key{" "}
            <strong className="text-text">{deleteTarget?.name}</strong>.
            Applications using this key will lose access.
          </>
        }
        submitLabel={
          deleteMode === "permanent" ? "Permanently Delete" : "Revoke Key"
        }
        submitDisabled={false}
        onSubmit={handleDelete}
      >
        <div className="space-y-2">
          <label className="text-xs font-mono text-text-muted block">
            Choose an action
          </label>
          <div className="space-y-2">
            <button
              type="button"
              onClick={() => setDeleteMode("revoke")}
              className={`flex items-center gap-2.5 w-full text-left px-3 py-2 border transition-colors ${
                deleteMode === "revoke"
                  ? "border-error/40 bg-error/5"
                  : "border-border bg-surface hover:bg-surface-hi"
              }`}
            >
              <span
                className={`flex-shrink-0 h-3.5 w-3.5 border flex items-center justify-center ${
                  deleteMode === "revoke"
                    ? "border-text-muted bg-surface-hi"
                    : "border-border bg-surface"
                }`}
              >
                {deleteMode === "revoke" && (
                  <Check className="h-2.5 w-2.5 text-text-muted" />
                )}
              </span>
              <div>
                <span className="text-xs font-mono text-text">Revoke</span>
                <p className="text-xs text-text-dim">
                  Deactivate the key. The record is kept for audit purposes.
                </p>
              </div>
            </button>
            <button
              type="button"
              onClick={() => setDeleteMode("permanent")}
              className={`flex items-center gap-2.5 w-full text-left px-3 py-2 border transition-colors ${
                deleteMode === "permanent"
                  ? "border-error/40 bg-error/5"
                  : "border-border bg-surface hover:bg-surface-hi"
              }`}
            >
              <span
                className={`flex-shrink-0 h-3.5 w-3.5 border flex items-center justify-center ${
                  deleteMode === "permanent"
                    ? "border-text-muted bg-surface-hi"
                    : "border-border bg-surface"
                }`}
              >
                {deleteMode === "permanent" && (
                  <Check className="h-2.5 w-2.5 text-text-muted" />
                )}
              </span>
              <div>
                <span className="text-xs font-mono text-primary">
                  Permanently delete
                </span>
                <p className="text-xs text-text-dim">
                  Remove the key record entirely. This cannot be undone.
                </p>
              </div>
            </button>
          </div>
        </div>
      </FormDialog>
    </div>
  );
}

/* ── Create key dialog ────────────────────────────────────────────────── */

function CreateKeyDialog({
  open,
  onOpenChange,
  orgId,
  onCreated,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  orgId: string;
  onCreated: () => void;
}) {
  const { toast } = useToast();

  const [name, setName] = useState("");
  const [expiration, setExpiration] = useState<string>(KeyExpiration.never);
  const [loading, setLoading] = useState(false);
  const [rawKey, setRawKey] = useState<string | null>(null);
  const [showKey, setShowKey] = useState(false);
  const [copied, setCopied] = useState(false);

  const created = rawKey !== null;

  function reset() {
    setName("");
    setExpiration(KeyExpiration.never);
    setRawKey(null);
    setShowKey(false);
    setCopied(false);
    setLoading(false);
  }

  function handleClose() {
    onOpenChange(false);
    // Defer reset so the closing animation plays with current content
    setTimeout(reset, 200);
  }

  async function handleCreate() {
    if (!name.trim()) return;
    setLoading(true);
    try {
      const result = await createAPIKey(orgId, {
        name: name.trim(),
        expiration: expiration as KeyExpiration,
      });
      setRawKey(result.raw_key);
      setShowKey(true);
      toast({ title: "API key created", variant: "success" });
      onCreated();
    } catch (err) {
      toast({ title: extractErrorMessage(err), variant: "error" });
    } finally {
      setLoading(false);
    }
  }

  function copyToClipboard() {
    if (!rawKey) return;
    navigator.clipboard.writeText(rawKey);
    toast({ title: "Copied to clipboard", variant: "success" });
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(v) => {
        if (!v) handleClose();
      }}
      title={created ? "Save your API key" : "Create new API key"}
      titleIcon={<KeyRound className="h-4 w-4" />}
      locked={loading || created}
    >
      {created ? (
        <div className="space-y-4">
          <div className="bg-warning/5 border border-warning/20 p-3 space-y-2">
            <p className="text-xs text-warning font-mono">
              Please copy and save your secret key in a safe place since you
              won&apos;t be able to view it again. If you do lose it,
              you&apos;ll need to generate a new one.
            </p>
            <div className="flex items-center gap-2">
              <code className="ph-no-capture flex-1 text-xs font-mono text-text bg-bg px-2 py-2 border border-border overflow-x-auto whitespace-nowrap scrollbar-hide">
                {showKey ? rawKey : "••••••••••••••••"}
              </code>
              <Tooltip content="Toggle visibility">
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={() => setShowKey(!showKey)}
                >
                  {showKey ? (
                    <EyeOff className="h-3 w-3" />
                  ) : (
                    <Eye className="h-3 w-3" />
                  )}
                </Button>
              </Tooltip>
              <Tooltip content={copied ? "Copied!" : "Copy"}>
                <Button variant="ghost" size="icon" onClick={copyToClipboard}>
                  {copied ? (
                    <Check className="h-3 w-3 text-success" />
                  ) : (
                    <Copy className="h-3 w-3" />
                  )}
                </Button>
              </Tooltip>
            </div>
          </div>
          <div className="flex justify-end">
            <Button size="sm" onClick={handleClose}>
              Done
            </Button>
          </div>
        </div>
      ) : (
        <div className="space-y-4">
          <div className="space-y-3">
            <div>
              <label className="text-xs font-mono text-text-muted block mb-1">
                Key Name
              </label>
              <Input
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="e.g. Production"
                autoFocus
                onKeyDown={(e) => {
                  if (e.key === "Enter" && name.trim() && !loading)
                    handleCreate();
                }}
              />
            </div>
            <div>
              <label className="text-xs font-mono text-text-muted block mb-1">
                Expiration
              </label>
              <Select value={expiration} onValueChange={setExpiration}>
                <SelectTrigger className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {Object.values(KeyExpiration).map((e) => (
                    <SelectItem key={e} value={e}>
                      {e}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>
          <div className="flex justify-end gap-2">
            <Button
              variant="secondary"
              size="sm"
              disabled={loading}
              onClick={handleClose}
            >
              Cancel
            </Button>
            <Button
              size="sm"
              disabled={loading || !name.trim()}
              onClick={handleCreate}
            >
              {loading && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
              Create API key
            </Button>
          </div>
        </div>
      )}
    </Dialog>
  );
}
