"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useOrganization } from "@/components/providers/OrganizationProvider";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";
import {
  getSubscription,
  getUsage,
  getBilling,
  getInvoices,
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
import { ExternalLink, Check, ChevronLeft, ChevronRight } from "lucide-react";
import type { SubscriptionPlan } from "@/lib/api/enums";
import type { PlanInfo, UsageHistoryItem } from "@/lib/api/types";

const CONTACT_URL = "https://www.pandaprobe.com/contact";

interface PlanMeta {
  features: string[];
  isEnterprise?: boolean;
}

const PLAN_META: Record<string, PlanMeta> = {
  HOBBY: {
    features: [
      "Human annotation",
      "Community support via GitHub",
    ],
  },
  PRO: {
    features: [
      "Email support",
    ],
  },
  STARTUP: {
    features: [
      "High rate limits",
      "Private Slack channel",
    ],
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
  const invoicesQuery = useQuery({
    queryKey: queryKeys.subscriptions.invoices(orgId),
    queryFn: () => getInvoices(orgId),
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
  const invoices = invoicesQuery.data ?? [];
  const plans = plansQuery.data ?? [];

  return (
    <div className="space-y-6 animate-fade-in">
      <h1 className="text-lg font-mono text-primary">Billing</h1>

      {/* ── Current Subscription ─────────────────────────────────── */}
      {subscription && (
        <div className="border-engraved bg-surface p-4">
          <h2 className="text-xs font-mono text-text-muted uppercase tracking-wider mb-3">
            Current Subscription
          </h2>
          <div className="grid grid-cols-2 md:grid-cols-5 gap-4 text-xs font-mono">
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
            <div>
              <span className="text-text-muted block">Canceled At</span>
              {subscription.canceled_at ? (
                <span className="text-error">
                  {formatDate(subscription.canceled_at)}
                </span>
              ) : (
                <Badge variant="default">N/A</Badge>
              )}
            </div>
          </div>
          <div className="mt-4">
            <Button variant="secondary" size="sm" onClick={handlePortal}>
              <ExternalLink className="h-3 w-3" /> Manage Billing
            </Button>
          </div>
        </div>
      )}

      {/* ── Current Period Usage ──────────────────────────────────── */}
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

      {/* ── Billing Breakdown ────────────────────────────────────── */}
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

      {/* ── Usage History / Invoices ──────────────────────────────── */}
      <InvoicesTable invoices={invoices} loading={invoicesQuery.isPending} />

      {/* ── Available Plans ───────────────────────────────────────── */}
      {plans.length > 0 && (
        <div className="border-engraved bg-surface p-4">
          <h2 className="text-xs font-mono text-text-muted uppercase tracking-wider mb-3">
            Available Plans
          </h2>
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
        </div>
      )}
    </div>
  );
}

const ROWS_PER_PAGE = 5;

function InvoicesTable({
  invoices,
  loading,
}: {
  invoices: UsageHistoryItem[];
  loading: boolean;
}) {
  const [page, setPage] = useState(0);
  const totalPages = Math.max(1, Math.ceil(invoices.length / ROWS_PER_PAGE));
  const pageInvoices = invoices.slice(
    page * ROWS_PER_PAGE,
    (page + 1) * ROWS_PER_PAGE,
  );

  return (
    <div className="border-engraved bg-surface p-4">
      <h2 className="text-xs font-mono text-text-muted uppercase tracking-wider mb-3">
        Billing History
      </h2>
      {loading ? (
        <p className="text-xs text-text-dim font-mono">Loading…</p>
      ) : invoices.length === 0 ? (
        <p className="text-xs text-text-dim font-mono">
          No usage history yet.
        </p>
      ) : (
        <>
          <div className="overflow-x-auto">
            <table className="w-full text-xs font-mono">
              <thead>
                <tr className="border-b border-border text-text-muted text-left">
                  <th className="px-3 py-2 font-normal">Period</th>
                  <th className="px-3 py-2 font-normal text-right">Traces</th>
                  <th className="px-3 py-2 font-normal text-right">
                    Trace Evals
                  </th>
                  <th className="px-3 py-2 font-normal text-right">
                    Session Evals
                  </th>
                  <th className="px-3 py-2 font-normal text-right">Billed</th>
                  <th className="px-3 py-2 font-normal text-right">Invoice</th>
                </tr>
              </thead>
              <tbody>
                {pageInvoices.map((inv, i) => (
                  <tr
                    key={page * ROWS_PER_PAGE + i}
                    className="border-b border-border/50 hover:bg-surface-hi transition-colors"
                  >
                    <td className="px-3 py-2 text-text-dim whitespace-nowrap">
                      {formatDate(inv.period_start)} –{" "}
                      {formatDate(inv.period_end)}
                    </td>
                    <td className="px-3 py-2 text-text text-right">
                      {formatNumber(inv.trace_count)}
                    </td>
                    <td className="px-3 py-2 text-text text-right">
                      {formatNumber(inv.trace_eval_count)}
                    </td>
                    <td className="px-3 py-2 text-text text-right">
                      {formatNumber(inv.session_eval_count)}
                    </td>
                    <td className="px-3 py-2 text-right">
                      {inv.billed ? (
                        <Badge variant="success">Billed</Badge>
                      ) : (
                        <Badge variant="default">Pending</Badge>
                      )}
                    </td>
                    <td className="px-3 py-2 text-text-dim text-right">
                      {inv.stripe_invoice_id ?? "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {totalPages > 1 && (
            <div className="flex items-center justify-between mt-3 text-xs font-mono text-text-dim">
              <span>
                Page {page + 1} of {totalPages}
              </span>
              <div className="flex items-center gap-1">
                <Button
                  variant="ghost"
                  size="icon"
                  disabled={page === 0}
                  onClick={() => setPage((p) => p - 1)}
                >
                  <ChevronLeft className="h-3 w-3" />
                </Button>
                <Button
                  variant="ghost"
                  size="icon"
                  disabled={page >= totalPages - 1}
                  onClick={() => setPage((p) => p + 1)}
                >
                  <ChevronRight className="h-3 w-3" />
                </Button>
              </div>
            </div>
          )}
        </>
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
