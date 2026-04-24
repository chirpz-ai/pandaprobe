"use client";

import { OrganizationProvider } from "@/components/providers/OrganizationProvider";
import { AuthGuard } from "@/components/features/AuthGuard";
import { SessionReplayController } from "@/components/providers/SessionReplayController";
import { Sidebar } from "@/components/features/Sidebar";
import { TopBar } from "@/components/features/TopBar";

export default function OrgLayout({ children }: { children: React.ReactNode }) {
  return (
    <OrganizationProvider>
      <AuthGuard>
        <SessionReplayController />
        <div className="flex h-screen overflow-hidden">
          <Sidebar />
          <div className="flex flex-1 flex-col min-w-0">
            <TopBar />
            <main className="flex-1 overflow-y-auto p-6">{children}</main>
          </div>
        </div>
      </AuthGuard>
    </OrganizationProvider>
  );
}
