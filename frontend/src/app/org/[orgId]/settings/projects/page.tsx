"use client";

import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { queryKeys } from "@/lib/query/keys";
import { useOrganization } from "@/components/providers/OrganizationProvider";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";
import { listProjects, createProject, deleteProject } from "@/lib/api/projects";
import { extractErrorMessage } from "@/lib/api/client";
import type { ProjectResponse } from "@/lib/api/types";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { LoadingState } from "@/components/common/LoadingState";
import { ErrorState } from "@/components/common/ErrorState";
import { EmptyState } from "@/components/common/EmptyState";
import { ConfirmDialog } from "@/components/common/ConfirmDialog";
import { useToast } from "@/components/providers/ToastProvider";
import { Plus, Trash2 } from "lucide-react";
import { formatDateTime } from "@/lib/utils/format";

export default function ProjectsPage() {
  const { currentOrg } = useOrganization();
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const orgId = currentOrg?.id ?? "";

  const [newName, setNewName] = useState("");
  const [newDesc, setNewDesc] = useState("");
  const [deleteTarget, setDeleteTarget] = useState<ProjectResponse | null>(
    null,
  );

  useDocumentTitle("Projects");

  const {
    data: projects = [],
    isPending,
    error,
    refetch,
  } = useQuery({
    queryKey: queryKeys.projects.list(orgId),
    queryFn: () => listProjects(orgId),
    enabled: !!currentOrg,
  });

  const invalidate = () =>
    queryClient.invalidateQueries({ queryKey: queryKeys.projects.all(orgId) });

  async function handleCreate() {
    if (!currentOrg || !newName.trim()) return;
    try {
      await createProject(currentOrg.id, {
        name: newName.trim(),
        description: newDesc.trim() || undefined,
      });
      toast({ title: "Project created", variant: "success" });
      setNewName("");
      setNewDesc("");
      invalidate();
    } catch (err) {
      toast({ title: extractErrorMessage(err), variant: "error" });
    }
  }

  async function handleDelete() {
    if (!currentOrg || !deleteTarget) return;
    try {
      await deleteProject(currentOrg.id, deleteTarget.id);
      toast({ title: "Project deleted", variant: "success" });
      setDeleteTarget(null);
      invalidate();
    } catch (err) {
      toast({ title: extractErrorMessage(err), variant: "error" });
    }
  }

  if (!currentOrg) return <EmptyState title="No organization selected" />;

  return (
    <div className="space-y-6 animate-fade-in">
      <h1 className="text-lg font-mono text-primary">Projects</h1>

      <div className="border-engraved bg-surface p-4">
        <div className="flex items-end gap-3">
          <div className="flex-1">
            <label className="text-xs font-mono text-text-muted block mb-1">
              Name
            </label>
            <Input
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              placeholder="Project name"
            />
          </div>
          <div className="flex-1">
            <label className="text-xs font-mono text-text-muted block mb-1">
              Description
            </label>
            <Input
              value={newDesc}
              onChange={(e) => setNewDesc(e.target.value)}
              placeholder="Optional"
            />
          </div>
          <Button size="sm" onClick={handleCreate} disabled={!newName.trim()}>
            <Plus className="h-3 w-3" /> Create
          </Button>
        </div>
      </div>

      {isPending ? (
        <LoadingState />
      ) : error ? (
        <ErrorState
          message={extractErrorMessage(error)}
          onRetry={() => refetch()}
        />
      ) : projects.length === 0 ? (
        <EmptyState
          title="No projects"
          description="Create a project to get started."
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
                  Description
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
              {projects.map((p) => (
                <tr
                  key={p.id}
                  className="border-b border-border hover:bg-surface-hi"
                >
                  <td className="px-3 py-2 text-text">{p.name}</td>
                  <td className="px-3 py-2 text-text-dim max-w-[300px] truncate">
                    {p.description || "—"}
                  </td>
                  <td className="px-3 py-2 text-text-dim">
                    {formatDateTime(p.created_at)}
                  </td>
                  <td className="px-3 py-2">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => setDeleteTarget(p)}
                    >
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
        title="Delete project"
        description={`Delete "${deleteTarget?.name}"? All associated data will be lost.`}
        confirmLabel="Delete"
        onConfirm={handleDelete}
        destructive
      />
    </div>
  );
}
