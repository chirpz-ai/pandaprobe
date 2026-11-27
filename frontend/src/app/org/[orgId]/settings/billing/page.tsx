"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useOrganization } from "@/components/providers/OrganizationProvider";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";
import {
  getSubscription,
  getBilling,
  getInvoices,
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
import { Tooltip } from "@/components/ui/Tooltip";
import { ExternalLink, ChevronLeft, ChevronRight } from "lucide-react";
import { SubscriptionPlan } from "@/lib/api/enums";
import type { UsageHistoryItem } from "@/lib/api/types";

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

  if (!currentOrg) return <EmptyState title="No organization selected" />;

  const loading =
    subQuery.isPending || billingQuery.isPending || invoicesQuery.isPending;
  const error = subQuery.error || billingQuery.error || invoicesQuery.error;

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
  const billing = billingQuery.data;
  const invoices = invoicesQuery.data ?? [];
  const contractBilling =
    billing?.plan === SubscriptionPlan.ENTERPRISE && !billing.pay_as_you_go;

  return (
    <div className="space-y-6 animate-fade-in">
      <h1 className="text-lg font-mono text-primary">Billing</h1>

      {/* ── Current Subscription ─────────────────────────────────── */}
      {subscription && (
        <div className="border-engraved bg-surface p-4">
          <h2 className="text-xs font-mono text-text-muted mb-3">
            Current subscription
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
            {subscription.plan === SubscriptionPlan.HOBBY ||
            subscription.plan === SubscriptionPlan.DEVELOPMENT ? (
              <Tooltip content="Upgrade to a paid plan to manage billing">
                <span className="inline-block">
                  <Button variant="secondary" size="sm" disabled>
                    <ExternalLink className="h-3 w-3" /> Manage Billing
                  </Button>
                </span>
              </Tooltip>
            ) : (
              <Button variant="secondary" size="sm" onClick={handlePortal}>
                <ExternalLink className="h-3 w-3" /> Manage Billing
              </Button>
            )}
          </div>
        </div>
      )}

      {/* ── Current Period Usage ──────────────────────────────────── */}
      {billing && (
        <div className="border-engraved bg-surface p-4">
          <h2 className="text-xs font-mono text-text-muted mb-3">
            Organization usage this period
          </h2>
          <p className="mb-3 text-sm font-mono text-text">
            {formatNumber(billing.total_events)} events used
            <span className="block text-xs text-text-muted">
              {billing.remaining_events === null
                ? "Unlimited events"
                : billing.included_events === 0 && billing.pay_as_you_go
                  ? "Pay-as-you-go events"
                  : `${formatNumber(billing.remaining_events)} of ${formatNumber(billing.included_events)} included events remaining`}
            </span>
          </p>
          <div className="grid grid-cols-3 gap-6 text-xs font-mono">
            <div>
              <span className="text-text-muted block">Traces</span>
              <span className="text-text text-lg">
                {formatNumber(billing.traces.used)}
              </span>
            </div>
            <div>
              <span className="text-text-muted block">Trace Evals</span>
              <span className="text-text text-lg">
                {formatNumber(billing.trace_evals.used)}
              </span>
            </div>
            <div>
              <span className="text-text-muted block">Session Evals</span>
              <span className="text-text text-lg">
                {formatNumber(billing.session_evals.used)}
              </span>
            </div>
          </div>
        </div>
      )}

      {/* ── Billing Breakdown ────────────────────────────────────── */}
      {contractBilling && (
        <p className="border-engraved bg-surface p-4 text-xs font-mono text-text-muted">
          Billed under your Enterprise agreement.
        </p>
      )}
      {billing && !contractBilling && (
        <div className="border-engraved bg-surface p-4">
          <h2 className="text-xs font-mono text-text-muted mb-3">
            Billing breakdown
          </h2>
          <div className="flex justify-between mb-2 text-xs font-mono">
            <span className="text-text-dim">Base subscription</span>
            <span>${(billing.base_price_cents / 100).toFixed(2)}</span>
          </div>
          {billing.pay_as_you_go && (
            <div className="mb-3 space-y-1 text-xs font-mono">
              <div className="flex justify-between">
                <span className="text-text-dim">Estimated overage</span>
                <span>${Number(billing.total_overage_cost).toFixed(2)}</span>
              </div>
              <p className="text-text-muted">
                {formatNumber(billing.overage_events)} current overage events at
                ${billing.overage_unit_price} each
              </p>
              {Number(billing.total_overage_cost) > 0 && (
                <p className="text-text-muted">
                  ${Number(billing.reported_overage_cost).toFixed(2)} reported
                  to Stripe · ${Number(billing.pending_overage_cost).toFixed(2)}{" "}
                  pending
                </p>
              )}
            </div>
          )}
          <div className="flex justify-between border-t border-divider pt-3">
            <span className="text-text-dim">Estimated Total</span>
            <span className="text-primary text-sm">
              ${(billing.estimated_total_cents / 100).toFixed(2)}
            </span>
          </div>
        </div>
      )}

      {/* ── Usage History / Invoices ──────────────────────────────── */}
      <InvoicesTable invoices={invoices} loading={invoicesQuery.isPending} />
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
      <h2 className="text-xs font-mono text-text-muted mb-3">
        Billing history
      </h2>
      {loading ? (
        <p className="text-xs text-text-dim font-mono">Loading…</p>
      ) : invoices.length === 0 ? (
        <p className="text-xs text-text-dim font-mono">No usage history yet.</p>
      ) : (
        <>
          <div className="overflow-x-auto">
            <table className="w-full text-xs font-mono">
              <thead>
                <tr className="border-b border-divider text-text-muted text-left">
                  <th className="px-3 py-2 font-normal">Period</th>
                  <th className="px-3 py-2 font-normal text-right">
                    Total events
                  </th>
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
                      {formatNumber(inv.total_events)}
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
