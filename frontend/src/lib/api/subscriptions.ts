import { client } from "./client";
import type {
  SubscriptionResponse,
  UsageResponse,
  BillingResponse,
  UsageHistoryItem,
  PlanInfo,
  CheckoutRequest,
  CheckoutResponse,
  PortalRequest,
  PortalResponse,
} from "./types";

export async function getSubscription(
  orgId: string,
): Promise<SubscriptionResponse> {
  const res = await client.get<SubscriptionResponse>(
    `/organizations/${orgId}/subscriptions`,
  );
  return res.data;
}

export async function getUsage(orgId: string): Promise<UsageResponse> {
  const res = await client.get<UsageResponse>(
    `/organizations/${orgId}/subscriptions/usage`,
  );
  return res.data;
}

export async function getBilling(orgId: string): Promise<BillingResponse> {
  const res = await client.get<BillingResponse>(
    `/organizations/${orgId}/subscriptions/billing`,
  );
  return res.data;
}

export async function getInvoices(
  orgId: string,
  limit = 12,
): Promise<UsageHistoryItem[]> {
  const res = await client.get<UsageHistoryItem[]>(
    `/organizations/${orgId}/subscriptions/invoices`,
    { params: { limit } },
  );
  return res.data;
}

export async function getPlans(): Promise<PlanInfo[]> {
  const res = await client.get<PlanInfo[]>("/subscriptions/plans");
  return res.data;
}

export async function createCheckout(
  orgId: string,
  data: CheckoutRequest,
): Promise<CheckoutResponse> {
  const res = await client.post<CheckoutResponse>(
    `/organizations/${orgId}/subscriptions/checkout`,
    data,
  );
  return res.data;
}

export async function createPortalSession(
  orgId: string,
  data: PortalRequest,
): Promise<PortalResponse> {
  const res = await client.post<PortalResponse>(
    `/organizations/${orgId}/subscriptions/portal`,
    data,
  );
  return res.data;
}
