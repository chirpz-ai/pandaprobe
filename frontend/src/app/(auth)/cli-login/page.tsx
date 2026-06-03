"use client";

import { Suspense, useEffect, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";
import { useAuth } from "@/components/providers/AuthProvider";
import { useToast } from "@/components/providers/ToastProvider";
import { extractErrorMessage } from "@/lib/api/client";
import { createCliAuthCode } from "@/lib/api/cli";
import { listOrganizations } from "@/lib/api/organizations";
import { listProjects } from "@/lib/api/projects";
import { queryKeys } from "@/lib/query/keys";
import { Button } from "@/components/ui/Button";
import { Spinner } from "@/components/ui/Spinner";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/Select";

const CARD =
  "relative z-10 w-full max-w-sm border-engraved bg-surface p-8 animate-fade-in";

interface CliParams {
  port: number;
  state: string;
  codeChallenge: string;
  label: string;
  cliVersion: string;
}

/** Parse and validate the CLI-supplied query params. Returns an error string when invalid. */
function parseCliParams(params: URLSearchParams): {
  value?: CliParams;
  error?: string;
} {
  const portRaw = params.get("port");
  const state = params.get("state");
  const codeChallenge = params.get("code_challenge");
  const method = params.get("code_challenge_method");

  const port = Number(portRaw);
  if (!portRaw || !Number.isInteger(port) || port < 1024 || port > 65535) {
    return {
      error:
        "Invalid loopback port. The CLI must supply a port between 1024 and 65535.",
    };
  }
  if (!state) {
    return { error: "Missing 'state' parameter from the CLI request." };
  }
  if (!codeChallenge) {
    return {
      error: "Missing PKCE 'code_challenge' parameter from the CLI request.",
    };
  }
  if (method !== "S256") {
    return { error: "Unsupported PKCE method. Only 'S256' is supported." };
  }

  return {
    value: {
      port,
      state,
      codeChallenge,
      label: params.get("label") || "cli",
      cliVersion: params.get("cli_version") || "",
    },
  };
}

function Card({ children }: { children: React.ReactNode }) {
  return <div className={CARD}>{children}</div>;
}

function Loading() {
  return (
    <Card>
      <div className="flex justify-center py-6">
        <Spinner size="lg" />
      </div>
    </Card>
  );
}

function CliLoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { user, loading: authLoading, authEnabled } = useAuth();
  const { toast } = useToast();

  const parsed = useMemo(() => parseCliParams(searchParams), [searchParams]);
  const cli = parsed.value;

  // Logged-in when auth is enabled; auth-disabled dev mode is treated as ready.
  const ready = !authEnabled || !!user;

  const [selectedOrgId, setSelectedOrgId] = useState("");
  const [selectedProjectId, setSelectedProjectId] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [loopbackUrl, setLoopbackUrl] = useState<string | null>(null);

  // Redirect to login (preserving all CLI params) when not authenticated.
  useEffect(() => {
    if (authEnabled && !authLoading && !user) {
      const here = window.location.pathname + window.location.search;
      router.replace(`/login?callbackUrl=${encodeURIComponent(here)}`);
    }
  }, [authEnabled, authLoading, user, router]);

  const orgsQuery = useQuery({
    queryKey: queryKeys.organizations.list(),
    queryFn: listOrganizations,
    enabled: ready && !parsed.error,
  });

  const orgs = useMemo(() => orgsQuery.data ?? [], [orgsQuery.data]);

  // Derive the effective org: explicit selection, else auto-select when there's exactly one.
  const effectiveOrgId = selectedOrgId || (orgs.length === 1 ? orgs[0].id : "");

  const projectsQuery = useQuery({
    queryKey: queryKeys.projects.list(effectiveOrgId),
    queryFn: () => listProjects(effectiveOrgId),
    enabled: ready && !!effectiveOrgId,
  });

  const projects = useMemo(
    () => projectsQuery.data ?? [],
    [projectsQuery.data],
  );

  // Derive the effective project. A stale selection from a previously chosen org
  // (not present in the current list) is ignored, falling back to single-project auto-select.
  const projectInList = projects.some((p) => p.id === selectedProjectId);
  const effectiveProjectId =
    (projectInList ? selectedProjectId : "") ||
    (projects.length === 1 ? projects[0].id : "");

  async function handleAuthorize() {
    if (!cli || !effectiveOrgId || !effectiveProjectId) {
      toast({
        title: "Select an organization and project first.",
        variant: "error",
      });
      return;
    }
    setSubmitting(true);
    try {
      const { code } = await createCliAuthCode({
        org_id: effectiveOrgId,
        project_id: effectiveProjectId,
        code_challenge: cli.codeChallenge,
        code_challenge_method: "S256",
        label: cli.label,
        expires_days: 90,
      });
      const url = `http://127.0.0.1:${cli.port}/callback?code=${encodeURIComponent(
        code,
      )}&state=${encodeURIComponent(cli.state)}`;
      setLoopbackUrl(url);
      window.location.assign(url);
    } catch (err) {
      toast({ title: extractErrorMessage(err), variant: "error" });
      setSubmitting(false);
    }
  }

  // --- Render states -------------------------------------------------------

  if (parsed.error) {
    return (
      <Card>
        <div className="mb-4 text-center">
          <h1 className="text-xl font-mono text-primary tracking-tight">
            Authorize CLI
          </h1>
        </div>
        <p className="text-xs text-error font-mono">{parsed.error}</p>
        <p className="mt-4 text-center text-xs text-text-muted">
          Re-run <span className="text-text-dim">pandaprobe auth login</span>{" "}
          from your terminal.
        </p>
      </Card>
    );
  }

  // Waiting on auth resolution / redirect to login.
  if (authEnabled && (authLoading || !user)) {
    return <Loading />;
  }

  if (loopbackUrl) {
    return (
      <Card>
        <div className="mb-4 text-center">
          <h1 className="text-xl font-mono text-primary tracking-tight">
            Authorized
          </h1>
        </div>
        <p className="text-sm text-text text-center">
          You can return to your terminal — the CLI has been authorized.
        </p>
        <p className="mt-4 text-center text-xs text-text-muted">
          Not redirected?{" "}
          <a
            href={loopbackUrl}
            className="text-text-dim underline underline-offset-4"
          >
            Click here
          </a>
          .
        </p>
      </Card>
    );
  }

  return (
    <Card>
      <div className="mb-8 text-center">
        <h1 className="text-xl font-mono text-primary tracking-tight">
          Authorize CLI
        </h1>
        <p className="mt-1 text-xs text-text-dim">
          Grant the PandaProbe CLI access to your project.
        </p>
      </div>

      <div className="space-y-4">
        <div>
          <label className="mb-1 block text-[11px] font-mono text-text-muted uppercase tracking-wider">
            Organization
          </label>
          <Select
            value={effectiveOrgId}
            onValueChange={setSelectedOrgId}
            disabled={orgsQuery.isLoading}
          >
            <SelectTrigger>
              <SelectValue
                placeholder={
                  orgsQuery.isLoading ? "Loading…" : "Select organization"
                }
              />
            </SelectTrigger>
            <SelectContent>
              {orgs.map((org) => (
                <SelectItem key={org.id} value={org.id}>
                  {org.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div>
          <label className="mb-1 block text-[11px] font-mono text-text-muted uppercase tracking-wider">
            Project
          </label>
          <Select
            value={effectiveProjectId}
            onValueChange={setSelectedProjectId}
            disabled={!effectiveOrgId || projectsQuery.isLoading}
          >
            <SelectTrigger>
              <SelectValue
                placeholder={
                  !effectiveOrgId
                    ? "Select an organization first"
                    : projectsQuery.isLoading
                      ? "Loading…"
                      : "Select project"
                }
              />
            </SelectTrigger>
            <SelectContent>
              {projects.map((project) => (
                <SelectItem key={project.id} value={project.id}>
                  {project.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <Button
          className="w-full"
          onClick={handleAuthorize}
          disabled={submitting || !effectiveOrgId || !effectiveProjectId}
        >
          {submitting ? <Spinner size="sm" /> : "Authorize"}
        </Button>
      </div>

      <p className="mt-6 text-center text-[11px] text-text-muted">
        A 90-day API key named after{" "}
        <span className="text-text-dim">{cli?.label}</span> will be created.
      </p>
    </Card>
  );
}

export default function CliLoginPage() {
  useDocumentTitle("Authorize CLI");
  return (
    <Suspense fallback={<Loading />}>
      <CliLoginForm />
    </Suspense>
  );
}
