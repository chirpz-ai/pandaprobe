"use client";

import { Button } from "@/components/ui/Button";

export default function RootError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <div className="flex h-screen w-full items-center justify-center bg-bg">
      <div className="text-center space-y-4 max-w-md px-6">
        <h1 className="text-lg font-mono text-primary">Something went wrong</h1>
        <p className="text-sm text-text-dim">
          {error.message || "An unexpected error occurred."}
        </p>
        {error.digest && (
          <p className="text-xs text-text-muted">Error ID: {error.digest}</p>
        )}
        <Button onClick={reset} variant="secondary">
          Try again
        </Button>
      </div>
    </div>
  );
}
