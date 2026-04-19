"use client";

import { useQuery } from "@tanstack/react-query";
import { useOrganization } from "@/components/providers/OrganizationProvider";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";
import {
  getSubscription,
  getPlans,
  createCheckout,
} from "@/lib/api/subscriptions";
import { queryKeys } from "@/lib/query/keys";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { LoadingState } from "@/components/common/LoadingState";
import { ErrorState } from "@/components/common/ErrorState";
import { EmptyState } from "@/components/common/EmptyState";
import { useToast } from "@/components/providers/ToastProvider";
import { extractErrorMessage } from "@/lib/api/client";
import { ExternalLink, Check } from "lucide-react";
import type { SubscriptionPlan } from "@/lib/api/enums";
import type { PlanInfo } from "@/lib/api/types";

const CONTACT_URL = "https://www.pandaprobe.com/contact";

interface PlanMeta {
  features: string[];
  isEnterprise?: boolean;
}

const PLAN_META: Record<string, PlanMeta> = {
  HOBBY: {
    features: ["Human annotation", "Community support via GitHub"],
  },
  PRO: {
    features: ["Email support"],
  },
  STARTUP: {
    features: ["High rate limits", "Private Slack channel"],
  },
  ENTERPRISE: {
    isEnterprise: true,
    features: [
      "Alternative hosting options",
      "Custom SSO",
      "Support SLA",
      "Team training",
      "Dedicated support",
    ],
  },
};

function formatLimit(v: number | null): string {
  if (v == null) return "Unlimited";
  if (v >= 1000) return `${(v / 1000).toLocaleString("en-US")}K`;
  return v.toLocaleString("en-US");
}

export default function PlansPage() {
  const { currentOrg } = useOrganization();
  const { toast } = useToast();
  const orgId = currentOrg?.id ?? "";

  useDocumentTitle("Plans");

  const subQuery = useQuery({
    queryKey: queryKeys.subscriptions.current(orgId),
    queryFn: () => getSubscription(orgId),
    enabled: !!currentOrg,
  });

  const plansQuery = useQuery({
    queryKey: queryKeys.subscriptions.plans,
    queryFn: getPlans,
  });

  if (!currentOrg) return <EmptyState title="No organization selected" />;

  const loading = subQuery.isPending || plansQuery.isPending;
  const error = subQuery.error || plansQuery.error;

  async function handleCheckout(plan: string) {
    try {
      const { checkout_url } = await createCheckout(orgId, {
        plan: plan as SubscriptionPlan,
        success_url: window.location.href,
        cancel_url: window.location.href,
      });
      window.location.assign(checkout_url);
    } catch (err) {
      toast({ title: extractErrorMessage(err), variant: "error" });
    }
  }

  if (loading) return <LoadingState />;
  if (error) return <ErrorState message={extractErrorMessage(error)} />;

  const subscription = subQuery.data;
  const plans = plansQuery.data ?? [];

  return (
    <div className="space-y-6 animate-fade-in">
      <div>
        <h1 className="text-lg font-mono text-primary">Plans</h1>
        <p className="text-xs font-mono text-text-muted mt-1">
          Choose the plan that fits your usage. You can upgrade or downgrade at
          any time from the billing portal.
        </p>
      </div>

      {plans.length === 0 ? (
        <EmptyState
          title="No plans available"
          description="Contact support if you expected plan options here."
        />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {plans.map((plan) => (
            <PlanCard
              key={plan.name}
              plan={plan}
              isCurrent={subscription?.plan === plan.name}
              onSelect={() => handleCheckout(plan.name)}
            />
          ))}
        </div>
      )}
    </div>
  );
}

function PlanCard({
  plan,
  isCurrent,
  onSelect,
}: {
  plan: PlanInfo;
  isCurrent: boolean;
  onSelect: () => void;
}) {
  const meta = PLAN_META[plan.name] ?? PLAN_META.HOBBY;

  const details: string[] = [];

  function usageLine(label: string, base: number | null): string {
    if (meta.isEnterprise) return `${label}: pay-as-you-go`;
    if (base != null || plan.pay_as_you_go) {
      const fmt = formatLimit(base);
      return plan.pay_as_you_go
        ? `${label}: ${fmt} / mo, then pay-as-you-go`
        : `${label}: ${fmt} / mo`;
    }
    return `${label}: Unlimited`;
  }

  details.push(usageLine("Traces", plan.base_traces));
  details.push(usageLine("Trace Evals", plan.base_trace_evals));
  details.push(usageLine("Session Evals", plan.base_session_evals));

  const seatLabel =
    plan.max_members == null
      ? "Unlimited seats"
      : plan.max_members === 1
        ? "1 seat"
        : `${plan.max_members} seats`;
  details.push(seatLabel);

  const allFeatures = [
    ...details,
    ...(plan.monitoring_allowed ? ["Monitoring"] : []),
    ...meta.features,
  ];

  return (
    <div className="border border-border p-4 space-y-2 flex flex-col">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-sm font-mono text-text">{plan.name}</span>
          {isCurrent && <Badge variant="info">Current</Badge>}
        </div>
        <span className="text-sm font-mono text-text">
          {meta.isEnterprise
            ? "Custom"
            : `$${(plan.monthly_price_cents / 100).toFixed(0)}/mo`}
        </span>
      </div>

      <div className="text-xs text-text-dim space-y-1.5 flex-1">
        {allFeatures.map((f) => (
          <div key={f} className="flex items-start gap-1.5">
            <Check className="h-3 w-3 flex-shrink-0 mt-0.5" />
            <span>{f}</span>
          </div>
        ))}
      </div>

      {meta.isEnterprise ? (
        <a
          href={CONTACT_URL}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center justify-center gap-1.5 w-full text-xs font-mono px-3 py-1.5 border border-border bg-surface hover:bg-surface-hi text-text transition-colors mt-2"
        >
          Contact <ExternalLink className="h-3 w-3" />
        </a>
      ) : isCurrent ? (
        <Button variant="secondary" size="sm" className="w-full mt-2" disabled>
          Current Plan
        </Button>
      ) : (
        <Button
          variant="secondary"
          size="sm"
          className="w-full mt-2"
          onClick={onSelect}
        >
          Select
        </Button>
      )}
    </div>
  );
}
