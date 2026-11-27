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
import {
  ChartColumn,
  ChevronLeft,
  ChevronRight,
  CreditCard,
  ExternalLink,
  History,
  ReceiptText,
  type LucideIcon,
} from "lucide-react";
import { SubscriptionPlan } from "@/lib/api/enums";
import type {
  BillingResponse,
  SubscriptionResponse,
  UsageHistoryItem,
} from "@/lib/api/types";

const usd = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
});

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
  return (
    <div className="@container/billing min-w-0 space-y-5 animate-fade-in">
      <h1 className="text-lg font-mono text-primary">Billing</h1>
      {subscription && (
        <SubscriptionCard subscription={subscription} onManage={handlePortal} />
      )}
      {billing && (
        <div className="grid items-start gap-4 @3xl:grid-cols-2 @3xl:items-stretch">
          <UsageCard billing={billing} />
          <BillingBreakdown billing={billing} />
        </div>
      )}
      <InvoicesTable invoices={invoices} />
    </div>
  );
}

function CardHeading({
  id,
  icon: Icon,
  children,
}: {
  id: string;
  icon: LucideIcon;
  children: string;
}) {
  return (
    <h2
      id={id}
      className="flex items-center gap-2 font-sans text-sm font-medium text-text"
    >
      <Icon aria-hidden="true" className="size-4 shrink-0 text-text-muted" />
      {children}
    </h2>
  );
}

function SubscriptionCard({
  subscription,
  onManage,
}: {
  subscription: SubscriptionResponse;
  onManage: () => void;
}) {
  const canManage =
    subscription.plan !== SubscriptionPlan.HOBBY &&
    subscription.plan !== SubscriptionPlan.DEVELOPMENT;
  const manageButton = (
    <Button
      variant="secondary"
      size="sm"
      onClick={onManage}
      disabled={!canManage}
    >
      Manage billing <ExternalLink aria-hidden="true" className="size-3" />
    </Button>
  );

  return (
    <section
      aria-labelledby="subscription-heading"
      className="grid items-center gap-x-6 gap-y-4 rounded-panel border border-border bg-surface p-4 font-sans @sm:grid-cols-[1fr_auto] @sm:p-5 @3xl:grid-cols-[auto_1fr_auto]"
    >
      <div>
        <CardHeading id="subscription-heading" icon={CreditCard}>
          Current subscription
        </CardHeading>
        <div className="mt-2 flex flex-wrap items-center gap-2.5">
          <span className="text-xl font-medium tracking-tight text-primary capitalize">
            {subscription.plan.toLowerCase()}
          </span>
          <StatusBadge status={subscription.status} />
        </div>
      </div>
      <dl className="flex flex-wrap gap-x-8 gap-y-3 border-t border-divider pt-3 @sm:col-span-2 @3xl:col-span-1 @3xl:col-start-2 @3xl:row-start-1 @3xl:border-l @3xl:border-t-0 @3xl:py-0 @3xl:pl-6">
        <div>
          <dt className="text-xs text-text-muted">Billing period</dt>
          <dd className="mt-1 text-sm tabular-nums text-text">
            <time dateTime={subscription.current_period_start}>
              {formatDate(subscription.current_period_start)}
            </time>
            {" – "}
            <time dateTime={subscription.current_period_end}>
              {formatDate(subscription.current_period_end)}
            </time>
          </dd>
        </div>
        {subscription.canceled_at && (
          <div>
            <dt className="text-xs text-text-muted">Canceled on</dt>
            <dd className="mt-1 text-sm tabular-nums text-text">
              <time dateTime={subscription.canceled_at}>
                {formatDate(subscription.canceled_at)}
              </time>
            </dd>
          </div>
        )}
      </dl>
      <div className="@sm:col-start-2 @sm:row-start-1 @sm:justify-self-end @3xl:col-start-3">
        {canManage ? (
          manageButton
        ) : (
          <Tooltip content="Upgrade to a paid plan to manage billing">
            <span tabIndex={0} className="inline-flex">
              {manageButton}
            </span>
          </Tooltip>
        )}
      </div>
    </section>
  );
}

function UsageCard({ billing }: { billing: BillingResponse }) {
  const included = billing.included_events;
  const remaining = billing.remaining_events;
  // Historical category allowances can have units left even when total usage exceeds their sum.
  const usedAllowance =
    included !== null && included > 0 && remaining !== null
      ? Math.max(0, Math.min(included, included - remaining))
      : null;

  return (
    <section
      aria-labelledby="usage-heading"
      className="@container/usage flex min-w-0 flex-col rounded-panel border border-border bg-surface font-sans"
    >
      <div className="flex-1 p-4 @sm/billing:p-5">
        <CardHeading id="usage-heading" icon={ChartColumn}>
          Organization usage this period
        </CardHeading>
        <p className="mt-4 flex flex-wrap items-baseline gap-x-2">
          <span className="break-all font-mono text-2xl font-medium leading-tight tracking-tight text-primary tabular-nums">
            {formatNumber(billing.total_events)}
          </span>{" "}
          <span className="text-sm text-text-dim">
            {billing.total_events === 1 ? "event used" : "events used"}
          </span>
        </p>
        {usedAllowance !== null && included !== null && (
          <div
            role="meter"
            aria-label="Included events used"
            aria-valuemin={0}
            aria-valuemax={included}
            aria-valuenow={usedAllowance}
            className="mt-3 h-1.5 overflow-hidden rounded-control bg-border"
          >
            <div
              className="h-full bg-info"
              style={{ width: `${(100 * usedAllowance) / included}%` }}
            />
          </div>
        )}
        <p className="mt-2 text-xs text-text-dim">
          {remaining === null
            ? "Unlimited events"
            : included === 0 && billing.pay_as_you_go
              ? "Pay-as-you-go events"
              : `${formatNumber(remaining)} of ${formatNumber(included)} included events remaining`}
        </p>
      </div>
      <dl className="grid gap-2 border-t border-divider px-4 py-3 @sm/billing:px-5 @xs/usage:grid-cols-3">
        {[
          { label: "Traces", used: billing.traces.used },
          { label: "Trace evaluations", used: billing.trace_evals.used },
          { label: "Session evaluations", used: billing.session_evals.used },
        ].map(({ label, used }) => (
          <div
            key={label}
            className="flex min-w-0 items-baseline justify-between gap-x-2 @xs/usage:block"
          >
            <dt className="text-xs text-text-muted">{label}</dt>
            <dd className="break-all font-mono text-sm tabular-nums text-text @xs/usage:mt-1">
              {formatNumber(used)}
            </dd>
          </div>
        ))}
      </dl>
    </section>
  );
}

function BillingBreakdown({ billing }: { billing: BillingResponse }) {
  const contractBilling =
    billing.plan === SubscriptionPlan.ENTERPRISE && !billing.pay_as_you_go;

  return (
    <section
      aria-labelledby="breakdown-heading"
      className="flex min-w-0 flex-col rounded-panel border border-border bg-surface p-4 font-sans @sm:p-5"
    >
      <CardHeading id="breakdown-heading" icon={ReceiptText}>
        Billing breakdown
      </CardHeading>
      {contractBilling ? (
        <p className="mt-4 text-sm text-text-dim">
          Billed under your Enterprise agreement.
        </p>
      ) : (
        <>
          <p className="mt-4 flex flex-wrap items-baseline gap-x-2">
            <span className="break-all font-mono text-2xl font-medium leading-tight tracking-tight text-primary tabular-nums">
              {usd.format(billing.estimated_total_cents / 100)}
            </span>{" "}
            <span className="text-sm text-text-dim">estimated total</span>
          </p>
          <dl className="mt-4 space-y-2 border-t border-divider pt-3 text-sm">
            <div className="flex items-baseline justify-between gap-3">
              <dt className="text-text-dim">Base subscription</dt>
              <dd className="font-mono tabular-nums text-text">
                {usd.format(billing.base_price_cents / 100)}
              </dd>
            </div>
            <div className="flex items-baseline justify-between gap-3">
              <dt className="text-text-dim">
                {billing.pay_as_you_go ? "Estimated overage" : "Event overage"}
              </dt>
              <dd className="text-right font-mono tabular-nums text-text">
                {billing.pay_as_you_go
                  ? usd.format(Number(billing.total_overage_cost))
                  : "Not billed"}
              </dd>
            </div>
          </dl>
          {billing.pay_as_you_go && (
            <div className="mt-2 space-y-2 border-l border-divider pl-3 text-xs text-text-muted">
              <p>
                {formatNumber(billing.overage_events)} current overage{" "}
                {billing.overage_events === 1 ? "event" : "events"} at $
                {billing.overage_unit_price} each
              </p>
              {Number(billing.total_overage_cost) > 0 && (
                <dl className="space-y-1">
                  <div className="flex justify-between gap-2">
                    <dt>Reported to Stripe</dt>
                    <dd className="font-mono tabular-nums text-text-dim">
                      {usd.format(Number(billing.reported_overage_cost))}
                    </dd>
                  </div>
                  <div className="flex justify-between gap-2">
                    <dt>Pending</dt>
                    <dd className="font-mono tabular-nums text-text-dim">
                      {usd.format(Number(billing.pending_overage_cost))}
                    </dd>
                  </div>
                </dl>
              )}
            </div>
          )}
        </>
      )}
    </section>
  );
}

const ROWS_PER_PAGE = 5;

function InvoicesTable({ invoices }: { invoices: UsageHistoryItem[] }) {
  const [page, setPage] = useState(0);
  const totalPages = Math.max(1, Math.ceil(invoices.length / ROWS_PER_PAGE));
  const pageInvoices = invoices.slice(
    page * ROWS_PER_PAGE,
    (page + 1) * ROWS_PER_PAGE,
  );

  return (
    <section
      aria-labelledby="history-heading"
      className="min-w-0 rounded-panel border border-border bg-surface p-4 @sm:p-5"
    >
      <div className="mb-3">
        <CardHeading id="history-heading" icon={History}>
          Billing history
        </CardHeading>
      </div>
      {invoices.length === 0 ? (
        <p className="text-xs text-text-dim font-mono">No usage history yet.</p>
      ) : (
        <>
          <div className="overflow-x-auto">
            <table
              aria-labelledby="history-heading"
              className="w-full text-xs font-mono tabular-nums"
            >
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
                {pageInvoices.map((inv) => (
                  <tr
                    key={inv.period_start}
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
                  aria-label="Previous billing history page"
                  disabled={page === 0}
                  onClick={() => setPage((p) => p - 1)}
                >
                  <ChevronLeft className="h-3 w-3" />
                </Button>
                <Button
                  variant="ghost"
                  size="icon"
                  aria-label="Next billing history page"
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
    </section>
  );
}
