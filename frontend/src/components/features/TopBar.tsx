"use client";

import { usePathname } from "next/navigation";
import { ChevronRight } from "lucide-react";
import { AUTH_ENABLED } from "@/lib/auth/firebase";

function getBreadcrumbs(pathname: string): string[] {
  const segments = pathname
    .replace("/dashboard", "")
    .split("/")
    .filter(Boolean);
  if (segments.length === 0) return ["Dashboard"];
  return ["Dashboard", ...segments.map((s) =>
    s.replace(/-/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())
  )];
}

export function TopBar() {
  const pathname = usePathname();
  const crumbs = getBreadcrumbs(pathname);

  return (
    <header className="flex items-center justify-between h-12 px-4 border-b border-border bg-surface">
      <nav className="flex items-center gap-1 text-xs font-mono">
        {crumbs.map((crumb, i) => (
          <span key={i} className="flex items-center gap-1">
            {i > 0 && <ChevronRight className="h-3 w-3 text-text-muted" />}
            <span
              className={
                i === crumbs.length - 1 ? "text-text" : "text-text-dim"
              }
            >
              {crumb}
            </span>
          </span>
        ))}
      </nav>

      {!AUTH_ENABLED && (
        <span className="px-2 py-0.5 text-[10px] font-mono uppercase tracking-wider text-warning border border-warning/30 bg-warning/5">
          Dev Mode
        </span>
      )}
    </header>
  );
}
