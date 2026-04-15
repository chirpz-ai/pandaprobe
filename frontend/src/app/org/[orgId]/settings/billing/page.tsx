"use client";

import { useQuery } from "@tanstack/react-query";
import { useOrganization } from "@/components/providers/OrganizationProvider";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";
import {
  getSubscription,
  getUsage,
  getBilling,
  getPlans,
  createCheckout,
  createPortalSession,
} from "@/lib/api/subscriptions";
import { queryKeys } from "@/lib/query/keys";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { LoadingState } from "@/components/common/LoadingState";
import { ErrorState } from "@/components/common/ErrorState";
import { EmptyState } from "@/components/common/EmptyState";
import { StatusBadge } from "@/components/common/StatusBadge";
import { useToast } from "@/components/providers/ToastProvider";
import { formatNumber, formatDate } from "@/lib/utils/format";
import { extractErrorMessage } from "@/lib/api/client";
import { ExternalLink } from "lucide-react";
import type { SubscriptionPlan } from "@/lib/api/enums";

export default function BillingPage() {
  const { currentOrg } = useOrganization();
  const { toast } = useToast();
  const orgId = currentOrg?.id ?? "";

  useDocumentTitle("Billing");

  const subQuery = useQuery({
    queryKey: queryKeys.subscriptions.current(orgId),
    queryFn: () => getSubscription(orgId),
    enabled: !!currentOrg,
  });
  const usageQuery = useQuery({
    queryKey: queryKeys.subscriptions.usage(orgId),
    queryFn: () => getUsage(orgId),
    enabled: !!currentOrg,
  });
  const billingQuery = useQuery({
    queryKey: queryKeys.subscriptions.billing(orgId),
    queryFn: () => getBilling(orgId),
    enabled: !!currentOrg,
  });
  const plansQuery = useQuery({
    queryKey: queryKeys.subscriptions.plans,
    queryFn: getPlans,
  });

  if (!currentOrg) return <EmptyState title="No organization selected" />;

  const loading =
    subQuery.isPending ||
    usageQuery.isPending ||
    billingQuery.isPending ||
    plansQuery.isPending;
  const error =
    subQuery.error ||
    usageQuery.error ||
    billingQuery.error ||
    plansQuery.error;

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

  async function handlePortal() {
    try {
      const { portal_url } = await createPortalSession(orgId, {
        return_url: window.location.href,
      });
      window.location.assign(portal_url);
    } catch (err) {
      toast({ title: extractErrorMessage(err), variant: "error" });
    }
  }

  if (loading) return <LoadingState />;
  if (error) return <ErrorState message={extractErrorMessage(error)} />;

  const subscription = subQuery.data;
  const usage = usageQuery.data;
  const billing = billingQuery.data;
  const plans = plansQuery.data ?? [];

  return (
    <div className="space-y-6 animate-fade-in">
      <h1 className="text-lg font-mono text-primary">Billing</h1>

      {subscription && (
        <div className="border-engraved bg-surface p-4">
          <h2 className="text-xs font-mono text-text-muted uppercase tracking-wider mb-3">
            Current Subscription
          </h2>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-xs font-mono">
            <div>
              <span className="text-text-muted block">Plan</span>
              <Badge variant="primary">{subscription.plan}</Badge>
            </div>
            <div>
              <span className="text-text-muted block">Status</span>
              <StatusBadge status={subscription.status} />
            </div>
            <div>
              <span className="text-text-muted block">Period Start</span>
              <span className="text-text">
                {formatDate(subscription.current_period_start)}
              </span>
            </div>
            <div>
              <span className="text-text-muted block">Period End</span>
              <span className="text-text">
                {formatDate(subscription.current_period_end)}
              </span>
            </div>
          </div>
          <div className="mt-4">
            <Button variant="secondary" size="sm" onClick={handlePortal}>
              <ExternalLink className="h-3 w-3" /> Manage Billing
            </Button>
          </div>
        </div>
      )}

      {usage && (
        <div className="border-engraved bg-surface p-4">
          <h2 className="text-xs font-mono text-text-muted uppercase tracking-wider mb-3">
            Current Period Usage
          </h2>
          <div className="grid grid-cols-3 gap-6 text-xs font-mono">
            <div>
              <span className="text-text-muted block">Traces</span>
              <span className="text-text text-lg">
                {formatNumber(usage.traces)}
              </span>
            </div>
            <div>
              <span className="text-text-muted block">Trace Evals</span>
              <span className="text-text text-lg">
                {formatNumber(usage.trace_evals)}
              </span>
            </div>
            <div>
              <span className="text-text-muted block">Session Evals</span>
              <span className="text-text text-lg">
                {formatNumber(usage.session_evals)}
              </span>
            </div>
          </div>
        </div>
      )}

      {billing && (
        <div className="border-engraved bg-surface p-4">
          <h2 className="text-xs font-mono text-text-muted uppercase tracking-wider mb-3">
            Billing Breakdown
          </h2>
          <div className="grid grid-cols-3 gap-4 text-xs font-mono mb-4">
            {(["traces", "trace_evals", "session_evals"] as const).map(
              (cat) => (
                <div key={cat} className="border border-border p-3">
                  <span className="text-text-muted block mb-1">
                    {cat.replace("_", " ")}
                  </span>
                  <div className="space-y-1">
                    <div className="flex justify-between">
                      <span className="text-text-dim">Used</span>
                      <span className="text-text">{billing[cat].used}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-text-dim">Included</span>
                      <span className="text-text">
                        {billing[cat].included ?? "Unlimited"}
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-text-dim">Overage</span>
                      <span className="text-warning">
                        {billing[cat].overage_cost}
                      </span>
                    </div>
                  </div>
                </div>
              ),
            )}
          </div>
          <div className="flex justify-between border-t border-border pt-3">
            <span className="text-text-dim">Estimated Total</span>
            <span className="text-primary text-sm">
              ${(billing.estimated_total_cents / 100).toFixed(2)}
            </span>
          </div>
        </div>
      )}

      {plans.length > 0 && (
        <div className="border-engraved bg-surface p-4">
          <h2 className="text-xs font-mono text-text-muted uppercase tracking-wider mb-3">
            Available Plans
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {plans.map((plan) => (
              <div
                key={plan.name}
                className="border border-border p-4 space-y-2"
              >
                <div className="flex items-center justify-between">
                  <span className="text-sm font-mono text-text">
                    {plan.name}
                  </span>
                  <span className="text-xs text-text-dim">
                    ${(plan.monthly_price_cents / 100).toFixed(0)}/mo
                  </span>
                </div>
                <div className="text-xs text-text-dim space-y-1">
                  <div>Traces: {plan.base_traces ?? "Unlimited"}</div>
                  <div>Trace Evals: {plan.base_trace_evals ?? "Unlimited"}</div>
                  <div>
                    Session Evals: {plan.base_session_evals ?? "Unlimited"}
                  </div>
                  {plan.monitoring_allowed && (
                    <Badge variant="info">Monitoring</Badge>
                  )}
                </div>
                {subscription?.plan !== plan.name && (
                  <Button
                    variant="secondary"
                    size="sm"
                    className="w-full mt-2"
                    onClick={() => handleCheckout(plan.name)}
                  >
                    Select
                  </Button>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
