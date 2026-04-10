"use client";

import { ProjectProvider } from "@/components/providers/ProjectProvider";

export default function ProjectLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <ProjectProvider>{children}</ProjectProvider>;
}
