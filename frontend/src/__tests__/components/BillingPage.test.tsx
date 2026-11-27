import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import BillingPage from "@/app/org/[orgId]/settings/billing/page";
import { SubscriptionPlan } from "@/lib/api/enums";
import { getBilling, getSubscription } from "@/lib/api/subscriptions";
import type { BillingResponse } from "@/lib/api/types";

jest.mock("@/components/providers/OrganizationProvider", () => ({
  useOrganization: () => ({ currentOrg: { id: "org-test" } }),
}));
jest.mock("@/components/providers/ToastProvider", () => ({
  useToast: () => ({ toast: jest.fn() }),
}));
jest.mock("@/lib/api/subscriptions", () => ({
  getBilling: jest.fn(),
  getInvoices: async () => [],
  getSubscription: jest.fn(),
}));

function renderBilling(billing: BillingResponse) {
  jest.mocked(getBilling).mockResolvedValue(billing);
  jest.mocked(getSubscription).mockResolvedValue({
    id: "sub-test",
    org_id: "org-test",
    plan: billing.plan,
    status: "ACTIVE",
    current_period_start: billing.period_start,
    current_period_end: billing.period_end,
    created_at: billing.period_start,
    canceled_at: null,
  });
  render(
    <QueryClientProvider client={new QueryClient()}>
      <BillingPage />
    </QueryClientProvider>,
  );
}

it("shows a pending charge even when live usage is back at the allowance", async () => {
  renderBilling({
    plan: SubscriptionPlan.STARTUP,
    period_start: "2026-09-01",
    period_end: "2026-10-01",
    base_price_cents: 29_900,
    pay_as_you_go: true,
    overage_unit_price: "0.004",
    traces: { used: 100_000 },
    trace_evals: { used: 0 },
    session_evals: { used: 0 },
    total_events: 100_000,
    included_events: 100_000,
    remaining_events: 0,
    overage_events: 0,
    total_overage_cost: "4",
    reported_overage_cost: "0",
    pending_overage_cost: "4",
    estimated_total_cents: 30_300,
  });
  expect(await screen.findByText("$303.00")).toBeInTheDocument();
  expect(screen.getByText(/0 current overage events/)).toBeInTheDocument();
  expect(
    screen.getByText("$0.00 reported to Stripe · $4.00 pending"),
  ).toBeInTheDocument();
});

it("shows unlimited Enterprise usage and identifies contract billing", async () => {
  renderBilling({
    plan: SubscriptionPlan.ENTERPRISE,
    period_start: "2026-09-01",
    period_end: "2026-10-01",
    base_price_cents: 0,
    pay_as_you_go: false,
    overage_unit_price: "0",
    traces: { used: 1_000_000 },
    trace_evals: { used: 200_000 },
    session_evals: { used: 50_000 },
    total_events: 1_250_000,
    included_events: null,
    remaining_events: null,
    overage_events: 0,
    total_overage_cost: "0",
    reported_overage_cost: "0",
    pending_overage_cost: "0",
    estimated_total_cents: 0,
  });
  expect(await screen.findByText("Unlimited events")).toBeInTheDocument();
  expect(screen.getByText("1,250,000 events used")).toBeInTheDocument();
  expect(
    screen.getByText("Billed under your Enterprise agreement."),
  ).toBeInTheDocument();
  expect(screen.queryByText("Estimated Total")).not.toBeInTheDocument();
});
