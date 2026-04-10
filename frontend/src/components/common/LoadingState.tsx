"use client";

import { Spinner } from "@/components/ui/Spinner";
import { SkeletonTable } from "@/components/ui/Skeleton";

interface LoadingStateProps {
  variant?: "spinner" | "table";
  rows?: number;
  cols?: number;
}

export function LoadingState({ variant = "table", rows = 6, cols = 5 }: LoadingStateProps) {
  if (variant === "table") {
    return <SkeletonTable rows={rows} cols={cols} />;
  }

  return (
    <div className="flex items-center justify-center py-16">
      <Spinner size="lg" />
    </div>
  );
}
