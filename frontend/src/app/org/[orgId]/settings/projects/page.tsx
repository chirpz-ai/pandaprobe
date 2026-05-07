"use client";

import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { queryKeys } from "@/lib/query/keys";
import { useOrganization } from "@/components/providers/OrganizationProvider";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";
import {
  listProjects,
  createProject,
  updateProject,
  deleteProject,
} from "@/lib/api/projects";
import { extractErrorMessage } from "@/lib/api/client";
import type { ProjectResponse } from "@/lib/api/types";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { LoadingState } from "@/components/common/LoadingState";
import { ErrorState } from "@/components/common/ErrorState";
import { EmptyState } from "@/components/common/EmptyState";
import { ConfirmDialog } from "@/components/common/ConfirmDialog";
import { FormDialog } from "@/components/common/FormDialog";
import { useToast } from "@/components/providers/ToastProvider";
import { Plus, Pencil, Trash2, Copy, Check } from "lucide-react";
import { Tooltip } from "@/components/ui/Tooltip";
import { formatDateTime } from "@/lib/utils/format";

export default function ProjectsPage() {
  const { currentOrg } = useOrganization();
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const orgId = currentOrg?.id ?? "";

  const [createOpen, setCreateOpen] = useState(false);
  const [newName, setNewName] = useState("");
  const [newDesc, setNewDesc] = useState("");
  const [editTarget, setEditTarget] = useState<ProjectResponse | null>(null);
  const [editName, setEditName] = useState("");
  const [editDesc, setEditDesc] = useState("");
  const [deleteTarget, setDeleteTarget] = useState<ProjectResponse | null>(
    null,
  );
  const [copiedId, setCopiedId] = useState<string | null>(null);

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

  function openCreate() {
    setNewName("");
    setNewDesc("");
    setCreateOpen(true);
  }

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
      throw err;
    }
  }

  function openEdit(p: ProjectResponse) {
    setEditTarget(p);
    setEditName(p.name);
    setEditDesc(p.description ?? "");
  }

  async function handleEdit() {
    if (!currentOrg || !editTarget || !editName.trim()) return;
    try {
      await updateProject(currentOrg.id, editTarget.id, {
        name: editName.trim(),
        description: editDesc.trim(),
      });
      toast({ title: "Project updated", variant: "success" });
      setEditTarget(null);
      invalidate();
    } catch (err) {
      toast({ title: extractErrorMessage(err), variant: "error" });
      throw err;
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
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-mono text-primary">Projects</h1>
        <Button size="sm" onClick={openCreate}>
          <Plus className="h-3 w-3" /> Create new project
        </Button>
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
                  <td className="px-3 py-2 text-text">
                    <div className="flex items-center gap-2">
                      <span>{p.name}</span>
                      <Tooltip content="Copy name">
                        <button
                          className="flex-shrink-0 text-text-muted hover:text-text transition-colors"
                          onClick={() => {
                            navigator.clipboard.writeText(p.name);
                            setCopiedId(p.id);
                            setTimeout(() => setCopiedId(null), 2000);
                          }}
                        >
                          {copiedId === p.id ? (
                            <Check className="h-3 w-3 text-success" />
                          ) : (
                            <Copy className="h-3 w-3" />
                          )}
                        </button>
                      </Tooltip>
                    </div>
                  </td>
                  <td className="px-3 py-2 text-text-dim max-w-[300px] truncate">
                    {p.description || "—"}
                  </td>
                  <td className="px-3 py-2 text-text-dim">
                    {formatDateTime(p.created_at)}
                  </td>
                  <td className="px-3 py-2">
                    <div className="flex items-center gap-1">
                      <Tooltip content="Edit">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => openEdit(p)}
                        >
                          <Pencil className="h-3 w-3" />
                        </Button>
                      </Tooltip>
                      <Tooltip content="Delete">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => setDeleteTarget(p)}
                        >
                          <Trash2 className="h-3 w-3 text-error" />
                        </Button>
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
        open={createOpen}
        onOpenChange={setCreateOpen}
        title="Create new project"
        titleIcon={<Plus className="h-4 w-4" />}
        submitLabel="Create project"
        submitDisabled={!newName.trim()}
        onSubmit={handleCreate}
      >
        <div>
          <label className="text-xs font-mono text-text-muted block mb-1">
            Name <span className="text-error">*</span>
          </label>
          <Input
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            placeholder="e.g. production"
            autoFocus
          />
        </div>
        <div>
          <label className="text-xs font-mono text-text-muted block mb-1">
            Description
          </label>
          <Input
            value={newDesc}
            onChange={(e) => setNewDesc(e.target.value)}
            placeholder="Optional"
          />
        </div>
      </FormDialog>

      <FormDialog
        open={!!editTarget}
        onOpenChange={(v) => {
          if (!v) setEditTarget(null);
        }}
        title="Edit Project"
        submitLabel="Save"
        submitDisabled={!editName.trim()}
        onSubmit={handleEdit}
      >
        <div>
          <label className="text-xs font-mono text-text-muted block mb-1">
            Name <span className="text-error">*</span>
          </label>
          <Input
            value={editName}
            onChange={(e) => setEditName(e.target.value)}
            placeholder="Project name"
            autoFocus
          />
        </div>
        <div>
          <label className="text-xs font-mono text-text-muted block mb-1">
            Description
          </label>
          <Input
            value={editDesc}
            onChange={(e) => setEditDesc(e.target.value)}
            placeholder="Optional"
          />
        </div>
      </FormDialog>

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
