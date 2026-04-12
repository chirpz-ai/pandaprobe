"use client";

import { Badge, type BadgeProps } from "@/components/ui/Badge";
import type {
  TraceStatus,
  EvaluationStatus,
  ScoreStatus,
  MonitorStatus,
} from "@/lib/api/enums";

type StatusType =
  | TraceStatus
  | EvaluationStatus
  | ScoreStatus
  | MonitorStatus
  | string;

const statusVariantMap: Record<string, BadgeProps["variant"]> = {
  COMPLETED: "success",
  OK: "success",
  SUCCESS: "success",
  ACTIVE: "success",
  RUNNING: "info",
  PENDING: "default",
  UNSET: "default",
  ERROR: "error",
  FAILED: "error",
  PAUSED: "warning",
  PAST_DUE: "warning",
  CANCELED: "error",
  INCOMPLETE: "warning",
};

export function StatusBadge({ status }: { status: StatusType }) {
  const variant = statusVariantMap[status] ?? "default";
  return <Badge variant={variant}>{status}</Badge>;
}
