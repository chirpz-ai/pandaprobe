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

export async function getSubscription(): Promise<SubscriptionResponse> {
  const res = await client.get<SubscriptionResponse>("/subscriptions");
  return res.data;
}

export async function getUsage(): Promise<UsageResponse> {
  const res = await client.get<UsageResponse>("/subscriptions/usage");
  return res.data;
}

export async function getBilling(): Promise<BillingResponse> {
  const res = await client.get<BillingResponse>("/subscriptions/billing");
  return res.data;
}

export async function getInvoices(
  limit = 12
): Promise<UsageHistoryItem[]> {
  const res = await client.get<UsageHistoryItem[]>("/subscriptions/invoices", {
    params: { limit },
  });
  return res.data;
}

export async function getPlans(): Promise<PlanInfo[]> {
  const res = await client.get<PlanInfo[]>("/subscriptions/plans");
  return res.data;
}

export async function createCheckout(
  data: CheckoutRequest
): Promise<CheckoutResponse> {
  const res = await client.post<CheckoutResponse>(
    "/subscriptions/checkout",
    data
  );
  return res.data;
}

export async function createPortalSession(
  data: PortalRequest
): Promise<PortalResponse> {
  const res = await client.post<PortalResponse>(
    "/subscriptions/portal",
    data
  );
  return res.data;
}
