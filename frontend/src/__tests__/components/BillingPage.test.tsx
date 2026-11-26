import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import BillingPage from "@/app/org/[orgId]/settings/billing/page";
import { SubscriptionPlan } from "@/lib/api/enums";
import { getBilling } from "@/lib/api/subscriptions";

jest.mock("@/components/providers/OrganizationProvider", () => ({
  useOrganization: () => ({ currentOrg: { id: "org-test" } }),
}));
jest.mock("@/components/providers/ToastProvider", () => ({
  useToast: () => ({ toast: jest.fn() }),
}));
jest.mock("@/lib/api/subscriptions", () => ({
  getBilling: jest.fn(),
  getInvoices: async () => [],
  getSubscription: async () => ({
    plan: "STARTUP",
    status: "ACTIVE",
    current_period_start: "2026-09-01",
    current_period_end: "2026-10-01",
  }),
}));

it("shows a pending charge even when live usage is back at the allowance", async () => {
  jest.mocked(getBilling).mockResolvedValue({
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
  const client = new QueryClient();
  render(
    <QueryClientProvider client={client}>
      <BillingPage />
    </QueryClientProvider>,
  );

  expect(await screen.findByText("$303.00")).toBeInTheDocument();
  expect(screen.getByText(/0 current overage events/)).toBeInTheDocument();
  expect(
    screen.getByText("$0.00 reported to Stripe · $4.00 pending"),
  ).toBeInTheDocument();
});
