"use client";

import { useQuery } from "@tanstack/react-query";
import { useOrganization } from "@/components/providers/OrganizationProvider";
import { useOrgId, useResolvedProjectId } from "@/hooks/useNavigation";
import { queryKeys } from "@/lib/query/keys";
import { listAPIKeys } from "@/lib/api/api-keys";
import { listTraces } from "@/lib/api/traces";

export interface OnboardingStatus {
  projectCreated: boolean;
  apiKeyCreated: boolean;
  traceIngested: boolean;
  allComplete: boolean;
  isLoading: boolean;
  projectId: string | null;
  orgId: string;
}

export function useOnboardingStatus(): OnboardingStatus {
  const orgId = useOrgId();
  const { projects, loading: orgLoading } = useOrganization();
  const projectId = useResolvedProjectId(projects);

  const apiKeysQuery = useQuery({
    queryKey: queryKeys.apiKeys.list(orgId),
    queryFn: () => listAPIKeys(orgId),
    enabled: !!orgId,
    staleTime: 60_000,
  });

  const tracesQuery = useQuery({
    queryKey: [
      ...queryKeys.dashboardStats.home(projectId),
      "onboarding-trace-probe",
    ],
    queryFn: () => listTraces({ limit: 1 }),
    enabled: !!projectId,
    staleTime: 60_000,
  });

  const projectCreated = projects.length > 0;
  const apiKeyCreated = (apiKeysQuery.data ?? []).some((k) => k.is_active);
  const traceIngested = (tracesQuery.data?.total ?? 0) > 0;

  const isLoading =
    orgLoading ||
    (!!orgId && apiKeysQuery.isPending) ||
    (projectCreated && tracesQuery.isPending);

  const allComplete = projectCreated && apiKeyCreated && traceIngested;

  return {
    projectCreated,
    apiKeyCreated,
    traceIngested,
    allComplete,
    isLoading,
    projectId,
    orgId,
  };
}
