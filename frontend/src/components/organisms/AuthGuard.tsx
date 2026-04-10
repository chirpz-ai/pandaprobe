"use client";

import { useEffect, type ReactNode } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/components/providers/AuthProvider";
import { Spinner } from "@/components/atoms/Spinner";

export function AuthGuard({ children }: { children: ReactNode }) {
  const { user, loading, authEnabled } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!loading && authEnabled && !user) {
      router.replace("/login");
    }
  }, [user, loading, authEnabled, router]);

  if (loading) {
    return (
      <div className="flex h-screen w-full items-center justify-center bg-bg">
        <Spinner size="lg" />
      </div>
    );
  }

  if (authEnabled && !user) {
    return null;
  }

  return <>{children}</>;
}
