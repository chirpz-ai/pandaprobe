"use client";

import { ProjectProvider } from "@/components/providers/ProjectProvider";
import { EvalRunTrackerProvider } from "@/components/providers/EvalRunTrackerProvider";

export default function ProjectLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <ProjectProvider>
      <EvalRunTrackerProvider>{children}</EvalRunTrackerProvider>
    </ProjectProvider>
  );
}
