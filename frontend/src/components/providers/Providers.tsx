"use client";

import type { ReactNode } from "react";
import { QueryClientProvider } from "@tanstack/react-query";
import { ReactQueryDevtools } from "@tanstack/react-query-devtools";
import { getQueryClient } from "@/lib/query/client";
import { AuthProvider } from "./AuthProvider";
import { PostHogProvider } from "./PostHogProvider";
import { ToastProvider } from "./ToastProvider";
import { ApiConfigProvider } from "./ApiConfigProvider";

export function Providers({ children }: { children: ReactNode }) {
  const queryClient = getQueryClient();

  return (
    <AuthProvider>
      <PostHogProvider>
        <ToastProvider>
          <QueryClientProvider client={queryClient}>
            <ApiConfigProvider>{children}</ApiConfigProvider>
            <ReactQueryDevtools initialIsOpen={false} />
          </QueryClientProvider>
        </ToastProvider>
      </PostHogProvider>
    </AuthProvider>
  );
}
