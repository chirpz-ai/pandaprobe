"use client";

import { Button } from "@/components/ui/Button";
import { useRouter } from "next/navigation";

export default function OrgError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  const router = useRouter();

  return (
    <div className="flex flex-1 items-center justify-center py-16">
      <div className="text-center space-y-4 max-w-md px-6">
        <h1 className="text-lg font-mono text-primary">Something went wrong</h1>
        <p className="text-sm text-text-dim">
          {error.message || "An unexpected error occurred."}
        </p>
        {error.digest && (
          <p className="text-xs text-text-muted">Error ID: {error.digest}</p>
        )}
        <div className="flex items-center justify-center gap-3">
          <Button onClick={reset} variant="secondary">
            Try again
          </Button>
          <Button onClick={() => router.push("/")} variant="ghost">
            Go home
          </Button>
        </div>
      </div>
    </div>
  );
}
