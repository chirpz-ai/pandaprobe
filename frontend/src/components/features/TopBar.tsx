"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { ChevronRight, ExternalLink } from "lucide-react";
import { AUTH_ENABLED } from "@/lib/auth/firebase";
import { DOCS_URL } from "@/lib/utils/constants";
import { Button } from "@/components/ui/Button";

const UUID_RE =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

interface Crumb {
  label: string;
  href: string;
}

function getBreadcrumbs(pathname: string): Crumb[] {
  const segments = pathname.split("/").filter(Boolean);

  let projectRoot: string | null = null;
  for (let i = 0; i + 3 < segments.length; i++) {
    if (
      segments[i] === "org" &&
      UUID_RE.test(segments[i + 1]) &&
      segments[i + 2] === "project" &&
      UUID_RE.test(segments[i + 3])
    ) {
      projectRoot = "/" + segments.slice(0, i + 4).join("/");
      break;
    }
  }

  const crumbs: Crumb[] = [];
  let accumulated = "";
  for (const seg of segments) {
    accumulated += "/" + seg;
    if (seg === "org" || seg === "project") continue;
    if (UUID_RE.test(seg)) continue;
    crumbs.push({
      label: seg.replace(/-/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()),
      href: accumulated,
    });
  }

  if (projectRoot) {
    if (crumbs.length === 0) {
      return [{ label: "Home", href: projectRoot }];
    }
    return [{ label: "Home", href: projectRoot }, ...crumbs];
  }

  if (crumbs.length === 0) return [{ label: "Home", href: "/" }];
  return crumbs;
}

export function TopBar() {
  const pathname = usePathname();
  const crumbs = getBreadcrumbs(pathname);

  return (
    <header className="flex items-center justify-between h-12 px-4 border-b border-border bg-surface">
      <nav className="flex items-center gap-1 text-xs font-mono">
        {crumbs.map((crumb, i) => {
          const isLast = i === crumbs.length - 1;
          return (
            <span key={crumb.href} className="flex items-center gap-1">
              {i > 0 && <ChevronRight className="h-3 w-3 text-text-muted" />}
              {isLast ? (
                <span className="text-text">{crumb.label}</span>
              ) : (
                <Link
                  href={crumb.href}
                  className="text-text-dim hover:text-text transition-colors"
                >
                  {crumb.label}
                </Link>
              )}
            </span>
          );
        })}
      </nav>

      <div className="flex items-center gap-3">
        {!AUTH_ENABLED && (
          <span className="px-2 py-0.5 text-[10px] font-mono uppercase tracking-wider text-warning border border-warning/30 bg-warning/5">
            Dev Mode
          </span>
        )}
        <Button variant="link" size="sm" asChild>
          <a href={DOCS_URL} target="_blank" rel="noopener noreferrer">
            Docs
            <ExternalLink className="h-3 w-3" />
          </a>
        </Button>
      </div>
    </header>
  );
}
