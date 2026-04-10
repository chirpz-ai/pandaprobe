"use client";

import type { ReactNode } from "react";
import { AuthProvider } from "./AuthProvider";
import { OrganizationProvider } from "./OrganizationProvider";
import { ProjectProvider } from "./ProjectProvider";
import { ToastProvider } from "./ToastProvider";
import { ApiConfigProvider } from "./ApiConfigProvider";

export function Providers({ children }: { children: ReactNode }) {
  return (
    <AuthProvider>
      <OrganizationProvider>
        <ProjectProvider>
          <ApiConfigProvider>
            <ToastProvider>{children}</ToastProvider>
          </ApiConfigProvider>
        </ProjectProvider>
      </OrganizationProvider>
    </AuthProvider>
  );
}
