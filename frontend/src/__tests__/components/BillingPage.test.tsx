import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
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

const startupBilling: BillingResponse = {
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
};

it("shows a pending charge even when live usage is back at the allowance", async () => {
  renderBilling(startupBilling);
  const breakdown = within(
    await screen.findByRole("region", { name: "Billing breakdown" }),
  );
  expect(breakdown.getByText("$303.00")).toBeInTheDocument();
  expect(
    breakdown.getByText("0 current overage events at $0.004 each"),
  ).toBeInTheDocument();
  expect(
    breakdown.getByText("Reported to Stripe").nextElementSibling,
  ).toHaveTextContent("$0.00");
  expect(breakdown.getByText("Pending").nextElementSibling).toHaveTextContent(
    "$4.00",
  );
  expect(
    screen.getByRole("meter", { name: "Included events used" }),
  ).toHaveAttribute("aria-valuenow", "100000");
});

it("shows the unused allowance in a historical period with category-specific overage", async () => {
  renderBilling({
    ...startupBilling,
    traces: { used: 105_000 },
    total_events: 105_000,
    included_events: 101_000,
    remaining_events: 51_000,
    overage_events: 55_000,
    total_overage_cost: "220",
    pending_overage_cost: "220",
    estimated_total_cents: 51_900,
  });
  const usage = within(
    await screen.findByRole("region", {
      name: "Organization usage this period",
    }),
  );
  const meter = usage.getByRole("meter", { name: "Included events used" });
  expect(meter).toHaveAttribute("aria-valuemax", "101000");
  expect(meter).toHaveAttribute("aria-valuenow", "50000");
  expect(
    usage.getByText("51,000 of 101,000 included events remaining"),
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
  expect(
    screen.getByRole("region", { name: "Organization usage this period" }),
  ).toHaveTextContent("1,250,000 events used");
  expect(screen.queryByRole("meter")).not.toBeInTheDocument();
  expect(
    screen.getByText("Billed under your Enterprise agreement."),
  ).toBeInTheDocument();
  expect(screen.queryByText(/estimated total/i)).not.toBeInTheDocument();
});
