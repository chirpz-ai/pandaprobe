"use client";

import type { ReactNode } from "react";
import Link from "next/link";
import { useMutation, useQuery } from "@tanstack/react-query";
import { ArrowRight, ArrowUpRight, Check, Server } from "lucide-react";
import { useOrganization } from "@/components/providers/OrganizationProvider";
import { useToast } from "@/components/providers/ToastProvider";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";
import {
  getSubscription,
  getPlans,
  createCheckout,
} from "@/lib/api/subscriptions";
import { extractErrorMessage } from "@/lib/api/client";
import { MembershipRole, SubscriptionPlan } from "@/lib/api/enums";
import type { PlanInfo } from "@/lib/api/types";
import { queryKeys } from "@/lib/query/keys";
import { formatNumber } from "@/lib/utils/format";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { LoadingState } from "@/components/common/LoadingState";
import { ErrorState } from "@/components/common/ErrorState";
import { EmptyState } from "@/components/common/EmptyState";

const CONTACT_URL = "https://www.pandaprobe.com/contact";
const monthlyPrice = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  trailingZeroDisplay: "stripIfInteger",
});

const planFeatures: Record<string, string[]> = {
  [SubscriptionPlan.HOBBY]: [
    "Human annotation",
    "Standard rate limits",
    "GitHub community support",
  ],
  [SubscriptionPlan.STARTUP]: [
    "Human annotation",
    "Higher rate limits",
    "Data retention controls",
    "Email and private Slack support",
  ],
  [SubscriptionPlan.ENTERPRISE]: [
    "Custom SSO and integrations",
    "Dedicated engineering support",
    "Uptime and support SLAs",
    "Team training and architecture guidance",
  ],
};

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
  const checkout = useMutation({
    mutationFn: () =>
      createCheckout(orgId, {
        plan: SubscriptionPlan.STARTUP,
        success_url: window.location.href,
        cancel_url: window.location.href,
      }),
    onSuccess: ({ checkout_url }) => window.location.assign(checkout_url),
    onError: (error) =>
      toast({ title: extractErrorMessage(error), variant: "error" }),
  });

  if (!currentOrg) return <EmptyState title="No organization selected" />;
  if (subQuery.isPending || plansQuery.isPending) return <LoadingState />;
  const error = subQuery.error || plansQuery.error;
  if (error) return <ErrorState message={extractErrorMessage(error)} />;

  const currentPlan = subQuery.data?.plan;
  const startupActionLabel =
    currentPlan === SubscriptionPlan.HOBBY
      ? "Upgrade to Startup"
      : "Choose Startup";
  const plans = plansQuery.data ?? [];
  const cloudPlans = plans.filter(
    (plan) => plan.name !== SubscriptionPlan.ENTERPRISE,
  );
  const enterprise = plans.find(
    (plan) => plan.name === SubscriptionPlan.ENTERPRISE,
  );
  const canManage =
    currentOrg.role === MembershipRole.OWNER ||
    currentOrg.role === MembershipRole.ADMIN;
  const billingPath = `/org/${orgId}/settings/billing`;

  return (
    <div className="@container/plans min-w-0 space-y-4 font-sans animate-fade-in">
      <h1 className="text-lg font-mono text-primary">Plans</h1>
      {plans.length === 0 ? (
        <EmptyState
          title="No plans available"
          description="Contact support if you expected plan options here."
        />
      ) : (
        <div className="grid gap-6 @2xl/plans:grid-cols-2">
          {cloudPlans.map((plan) => (
            <CloudPlanCard
              key={plan.name}
              plan={plan}
              isCurrent={plan.name === currentPlan}
            >
              {plan.name === SubscriptionPlan.STARTUP &&
              plan.name !== currentPlan ? (
                <Button
                  className="w-full font-sans"
                  disabled={!canManage || checkout.isPending}
                  onClick={() => checkout.mutate()}
                >
                  {!canManage
                    ? "Ask an admin to change plans"
                    : checkout.isPending
                      ? "Opening checkout…"
                      : startupActionLabel}
                  {canManage && !checkout.isPending && (
                    <ArrowRight aria-hidden="true" className="size-4" />
                  )}
                </Button>
              ) : (
                <Button
                  asChild
                  variant="secondary"
                  className="w-full font-sans"
                >
                  <Link href={billingPath}>
                    {plan.name === SubscriptionPlan.HOBBY &&
                    currentPlan === SubscriptionPlan.STARTUP &&
                    canManage
                      ? "Manage in billing"
                      : "View billing"}
                    <ArrowRight aria-hidden="true" className="size-4" />
                  </Link>
                </Button>
              )}
            </CloudPlanCard>
          ))}
          {enterprise && (
            <EnterpriseCard
              plan={enterprise}
              isCurrent={currentPlan === enterprise.name}
            />
          )}
        </div>
      )}
    </div>
  );
}

function CurrentPlanBadge() {
  return (
    <Badge
      variant="success"
      className="whitespace-nowrap font-sans font-medium"
    >
      Current plan
    </Badge>
  );
}

function PlanLimits({ plan }: { plan: PlanInfo }) {
  return (
    <dl className="grid grid-cols-2 gap-4">
      <div>
        <dt className="text-xs text-text-muted">Events per month</dt>
        <dd className="mt-0.5 text-lg font-medium tabular-nums text-text">
          {plan.included_events === null
            ? "Unlimited"
            : formatNumber(plan.included_events)}
        </dd>
      </div>
      <div>
        <dt className="text-xs text-text-muted">Seats</dt>
        <dd className="mt-0.5 text-lg font-medium tabular-nums text-text">
          {plan.max_members === null
            ? "Unlimited"
            : formatNumber(plan.max_members)}
        </dd>
      </div>
    </dl>
  );
}

function PlanFeatures({ plan }: { plan: PlanInfo }) {
  const features = [
    ...(planFeatures[plan.name] ?? []),
    ...(plan.monitoring_allowed ? ["Automated monitoring"] : []),
  ];
  return (
    <ul className="grid content-start gap-x-4 gap-y-1 text-sm text-text-dim @sm/details:grid-cols-2">
      {features.map((feature) => (
        <li key={feature} className="flex items-start gap-2">
          <Check
            aria-hidden="true"
            className="mt-1 size-3.5 shrink-0 text-text-muted"
          />
          <span>{feature}</span>
        </li>
      ))}
    </ul>
  );
}

function PlanCardHeader({
  plan,
  isCurrent,
}: {
  plan: PlanInfo;
  isCurrent: boolean;
}) {
  const isEnterprise = plan.name === SubscriptionPlan.ENTERPRISE;

  return (
    <header
      className={
        isEnterprise
          ? "grid gap-3"
          : "flex flex-wrap items-baseline justify-between gap-x-4 gap-y-2"
      }
    >
      <div className="flex flex-1 flex-wrap items-center gap-2">
        <h2
          id={`title-${plan.name}`}
          className="flex items-center gap-2 text-lg font-medium tracking-tight text-primary"
        >
          {isEnterprise && (
            <Server
              aria-hidden="true"
              className="size-4 shrink-0 text-text-muted"
            />
          )}
          {plan.name.charAt(0).toUpperCase() + plan.name.slice(1).toLowerCase()}
        </h2>
        {isCurrent && <CurrentPlanBadge />}
      </div>
      <p className="flex items-baseline gap-1 whitespace-nowrap text-text-dim">
        <span className="text-2xl font-medium tracking-tight tabular-nums text-primary">
          {isEnterprise
            ? "Custom pricing"
            : monthlyPrice.format(plan.monthly_price_cents / 100)}
        </span>
        {!isEnterprise && <span className="text-xs">/ month</span>}
      </p>
    </header>
  );
}

function CloudPlanCard({
  plan,
  isCurrent,
  children,
}: {
  plan: PlanInfo;
  isCurrent: boolean;
  children: ReactNode;
}) {
  return (
    <article
      aria-labelledby={`title-${plan.name}`}
      className="flex min-w-0 flex-col rounded-panel border border-border bg-surface px-4 py-3"
    >
      <PlanCardHeader plan={plan} isCurrent={isCurrent} />
      <div className="mt-2.5 border-y border-divider py-2">
        <PlanLimits plan={plan} />
        <p className="mt-1 text-xs text-text-dim">
          {plan.pay_as_you_go
            ? `$${plan.overage_unit_price} per additional event.`
            : "Usage stops at the monthly limit. No overage charges."}
        </p>
      </div>
      <div className="@container/details my-2.5 flex-1">
        <PlanFeatures plan={plan} />
      </div>
      {children}
    </article>
  );
}

function EnterpriseCard({
  plan,
  isCurrent,
}: {
  plan: PlanInfo;
  isCurrent: boolean;
}) {
  return (
    <section
      aria-labelledby={`title-${plan.name}`}
      className="col-span-full grid min-w-0 rounded-panel border border-border bg-surface @2xl/plans:grid-cols-[minmax(20rem,1fr)_minmax(0,1.5fr)]"
    >
      <div className="p-4 @sm/plans:p-5">
        <PlanCardHeader plan={plan} isCurrent={isCurrent} />
        <p className="mt-1 text-sm text-text-dim">
          Deploy in your VPC or on-premises with a committed-spend commercial
          license.
        </p>
        <Button asChild variant="secondary" className="mt-4 font-sans">
          <a href={CONTACT_URL} target="_blank" rel="noopener noreferrer">
            Talk to sales <ArrowUpRight aria-hidden="true" className="size-4" />
          </a>
        </Button>
      </div>
      <div className="@container/details border-t border-divider p-4 @sm/plans:p-5 @2xl/plans:border-l @2xl/plans:border-t-0">
        <PlanLimits plan={plan} />
        <div className="mt-3 border-t border-divider pt-3">
          <PlanFeatures plan={plan} />
        </div>
      </div>
    </section>
  );
}
