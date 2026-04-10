"use client";

import type { ReactNode } from "react";
import { AuthProvider } from "./AuthProvider";
import { ToastProvider } from "./ToastProvider";
import { ApiConfigProvider } from "./ApiConfigProvider";

export function Providers({ children }: { children: ReactNode }) {
  return (
    <AuthProvider>
      <ToastProvider>
        <ApiConfigProvider>{children}</ApiConfigProvider>
      </ToastProvider>
    </AuthProvider>
  );
}
