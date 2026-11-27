import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import PlansPage from "@/app/org/[orgId]/settings/plans/page";
import {
  getPlans,
  getSubscription,
  createCheckout,
} from "@/lib/api/subscriptions";
import { MembershipRole, SubscriptionPlan } from "@/lib/api/enums";
import type { PlanInfo } from "@/lib/api/types";

let mockRole: MembershipRole = MembershipRole.OWNER;
const mockToast = jest.fn();
jest.mock("@/components/providers/OrganizationProvider", () => ({
  useOrganization: () => ({ currentOrg: { id: "org-test", role: mockRole } }),
}));
jest.mock("@/components/providers/ToastProvider", () => ({
  useToast: () => ({ toast: mockToast }),
}));
jest.mock("@/lib/api/subscriptions", () => ({
  getPlans: jest.fn(),
  getSubscription: jest.fn(),
  createCheckout: jest.fn(),
}));

const hobby: PlanInfo = {
  name: SubscriptionPlan.HOBBY,
  included_events: 1_000,
  max_members: 1,
  monthly_price_cents: 0,
  overage_unit_price: "0.004",
  monitoring_allowed: false,
  pay_as_you_go: false,
};
const startup: PlanInfo = {
  ...hobby,
  name: SubscriptionPlan.STARTUP,
  included_events: 100_000,
  max_members: 10,
  monthly_price_cents: 29_900,
  monitoring_allowed: true,
  pay_as_you_go: true,
};
const enterprise: PlanInfo = {
  ...hobby,
  name: SubscriptionPlan.ENTERPRISE,
  included_events: null,
  max_members: null,
  overage_unit_price: "0",
  monitoring_allowed: true,
};

function renderPlans(
  currentPlan: SubscriptionPlan,
  plans = [hobby, startup, enterprise],
) {
  jest.mocked(getPlans).mockResolvedValue(plans);
  jest.mocked(getSubscription).mockResolvedValue({
    id: "sub-test",
    org_id: "org-test",
    plan: currentPlan,
    status: "ACTIVE",
    current_period_start: "2026-09-01",
    current_period_end: "2026-10-01",
    canceled_at: null,
    created_at: "2026-09-01",
  });
  render(
    <QueryClientProvider client={new QueryClient()}>
      <PlansPage />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  jest.clearAllMocks();
  mockRole = MembershipRole.OWNER;
});

it("uses the catalog for cloud terms and distinguishes unlimited Enterprise usage from a free plan", async () => {
  renderPlans(SubscriptionPlan.ENTERPRISE, [
    hobby,
    {
      ...startup,
      included_events: 123_456,
      monthly_price_cents: 32_950,
      overage_unit_price: "0.005",
    },
    enterprise,
  ]);
  const paid = within(await screen.findByRole("article", { name: /startup/i }));
  expect(paid.getByRole("button", { name: "Choose Startup" })).toBeEnabled();
  expect(paid.getByText("123,456")).toBeInTheDocument();
  expect(paid.getByText("$329.50")).toBeInTheDocument();
  expect(paid.getByText("$0.005 per additional event.")).toBeInTheDocument();
  const contract = within(screen.getByRole("region", { name: "Enterprise" }));
  expect(contract.getByText("Current plan")).toBeInTheDocument();
  expect(contract.getByText("Custom pricing")).toBeInTheDocument();
  expect(contract.getAllByText("Unlimited")).toHaveLength(2);
  expect(contract.queryByText(/\$0/)).not.toBeInTheDocument();
  expect(contract.getByRole("link", { name: "Talk to sales" })).toHaveAttribute(
    "href",
    "https://www.pandaprobe.com/contact",
  );
  const free = within(screen.getByRole("article", { name: /hobby/i }));
  expect(free.queryByText("Automated monitoring")).not.toBeInTheDocument();
  expect(free.getByText(/No overage charges/)).toBeInTheDocument();
});

it("starts Startup checkout for an admin and recovers when opening checkout fails", async () => {
  mockRole = MembershipRole.ADMIN;
  jest
    .mocked(createCheckout)
    .mockRejectedValueOnce(new Error("Checkout unavailable"));
  const user = userEvent.setup();
  renderPlans(SubscriptionPlan.HOBBY);
  const button = await screen.findByRole("button", {
    name: "Upgrade to Startup",
  });
  await user.click(button);
  expect(createCheckout).toHaveBeenCalledWith("org-test", {
    plan: SubscriptionPlan.STARTUP,
    success_url: window.location.href,
    cancel_url: window.location.href,
  });
  expect(mockToast).toHaveBeenCalledWith({
    title: "Checkout unavailable",
    variant: "error",
  });
  expect(
    await screen.findByRole("button", { name: "Upgrade to Startup" }),
  ).toBeEnabled();
});

it("routes a Startup owner to billing to manage their plan without starting a new checkout", async () => {
  renderPlans(SubscriptionPlan.STARTUP);
  const free = within(await screen.findByRole("article", { name: /hobby/i }));
  expect(free.getByRole("link", { name: "Manage in billing" })).toHaveAttribute(
    "href",
    "/org/org-test/settings/billing",
  );
  const paid = within(screen.getByRole("article", { name: /startup/i }));
  expect(paid.getByText("Current plan")).toBeInTheDocument();
  expect(paid.getByRole("link", { name: "View billing" })).toHaveAttribute(
    "href",
    "/org/org-test/settings/billing",
  );
  expect(paid.queryByRole("button")).not.toBeInTheDocument();
});

it("explains who can change plans to a member viewing Startup", async () => {
  mockRole = MembershipRole.MEMBER;
  renderPlans(SubscriptionPlan.HOBBY);
  expect(
    await screen.findByRole("button", { name: "Ask an admin to change plans" }),
  ).toBeDisabled();
});
