"use client";

import { useState } from "react";
import { Check, Copy, Eye, EyeOff, KeyRound, Loader2 } from "lucide-react";
import { createAPIKey } from "@/lib/api/api-keys";
import { extractErrorMessage } from "@/lib/api/client";
import { KeyExpiration } from "@/lib/api/enums";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Tooltip } from "@/components/ui/Tooltip";
import { Dialog } from "@/components/common/Dialog";
import { useToast } from "@/components/providers/ToastProvider";
import {
  Select,
  SelectTrigger,
  SelectContent,
  SelectItem,
  SelectValue,
} from "@/components/ui/Select";

interface APIKeyDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  orgId: string;
  onCreated?: () => void;
}

export function APIKeyDialog({
  open,
  onOpenChange,
  orgId,
  onCreated,
}: APIKeyDialogProps) {
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
      onCreated?.();
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
                Key Name <span className="text-error">*</span>
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
