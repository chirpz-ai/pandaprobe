"use client";

import { Spinner } from "@/components/ui/Spinner";

export function LoadingState() {
  return (
    <div className="flex items-center justify-center py-16">
      <Spinner size="lg" />
    </div>
  );
}
