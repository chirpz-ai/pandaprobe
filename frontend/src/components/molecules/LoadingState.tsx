"use client";

import { Spinner } from "@/components/atoms/Spinner";

export function LoadingState() {
  return (
    <div className="flex items-center justify-center py-16">
      <Spinner size="lg" />
    </div>
  );
}
