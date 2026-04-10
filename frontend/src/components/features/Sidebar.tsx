"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  LayoutDashboard,
  ListTree,
  Layers,
  CheckCircle,
  BarChart3,
  Building2,
  Users,
  FolderKanban,
  KeyRound,
  CreditCard,
  ChevronLeft,
  ChevronRight,
  LogOut,
  ChevronsUpDown,
} from "lucide-react";
import { cn } from "@/lib/utils/cn";
import { useAuth } from "@/components/providers/AuthProvider";
import { useOrganization } from "@/components/providers/OrganizationProvider";
import { useOrgId, useResolvedProjectId } from "@/hooks/useNavigation";
import * as Tooltip from "@radix-ui/react-tooltip";
import * as DropdownMenu from "@radix-ui/react-dropdown-menu";

const STORAGE_KEY = "pandaprobe_sidebar_collapsed";

interface NavItem {
  label: string;
  href: string;
  icon: React.ReactNode;
  exact?: boolean;
}

function NavLink({
  item,
  collapsed,
  active,
}: {
  item: NavItem;
  collapsed: boolean;
  active: boolean;
}) {
  const link = (
    <Link
      href={item.href}
      className={cn(
        "flex items-center gap-3 px-3 py-2 text-sm font-mono transition-colors duration-150",
        active
          ? "bg-surface-hi text-primary border-l-2 border-primary"
          : "text-text-dim hover:text-text hover:bg-surface-hi border-l-2 border-transparent",
        collapsed && "justify-center px-2"
      )}
    >
      {item.icon}
      {!collapsed && <span className="truncate">{item.label}</span>}
    </Link>
  );

  if (collapsed) {
    return (
      <Tooltip.Root>
        <Tooltip.Trigger asChild>{link}</Tooltip.Trigger>
        <Tooltip.Portal>
          <Tooltip.Content
            side="right"
            sideOffset={8}
            className="z-50 bg-surface border border-border px-2 py-1 text-xs font-mono text-text"
          >
            {item.label}
          </Tooltip.Content>
        </Tooltip.Portal>
      </Tooltip.Root>
    );
  }
  return link;
}

export function Sidebar() {
  const pathname = usePathname();
  const router = useRouter();
  const { signOut, authEnabled, user } = useAuth();
  const { organizations, currentOrg, projects } = useOrganization();
  const orgId = useOrgId();
  const resolvedProjectId = useResolvedProjectId(projects);

  const [collapsed, setCollapsed] = useState(false);

  useEffect(() => {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored === "true") setCollapsed(true);
  }, []);

  const orgBase = `/org/${orgId}`;
  const projectBase = resolvedProjectId
    ? `${orgBase}/project/${resolvedProjectId}`
    : null;

  const mainNav = useMemo<NavItem[]>(
    () => [
      {
        label: "Home",
        href: orgBase,
        icon: <LayoutDashboard className="h-4 w-4" />,
        exact: true,
      },
      {
        label: "Traces",
        href: projectBase ? `${projectBase}/traces` : orgBase,
        icon: <ListTree className="h-4 w-4" />,
      },
      {
        label: "Sessions",
        href: projectBase ? `${projectBase}/sessions` : orgBase,
        icon: <Layers className="h-4 w-4" />,
      },
      {
        label: "Evaluations",
        href: projectBase ? `${projectBase}/evaluations` : orgBase,
        icon: <CheckCircle className="h-4 w-4" />,
      },
      {
        label: "Analytics",
        href: projectBase ? `${projectBase}/analytics` : orgBase,
        icon: <BarChart3 className="h-4 w-4" />,
      },
    ],
    [orgBase, projectBase]
  );

  const settingsNav = useMemo<NavItem[]>(
    () => [
      { label: "Organization", href: `${orgBase}/settings/organization`, icon: <Building2 className="h-4 w-4" /> },
      { label: "Members", href: `${orgBase}/settings/members`, icon: <Users className="h-4 w-4" /> },
      { label: "Projects", href: `${orgBase}/settings/projects`, icon: <FolderKanban className="h-4 w-4" /> },
      { label: "API Keys", href: `${orgBase}/settings/api-keys`, icon: <KeyRound className="h-4 w-4" /> },
      { label: "Billing", href: `${orgBase}/settings/billing`, icon: <CreditCard className="h-4 w-4" /> },
    ],
    [orgBase]
  );

  function isActive(item: NavItem): boolean {
    if (item.exact) return pathname === item.href;
    return pathname.startsWith(item.href) && item.href !== orgBase;
  }

  function toggleCollapsed() {
    const next = !collapsed;
    setCollapsed(next);
    localStorage.setItem(STORAGE_KEY, String(next));
  }

  function switchOrg(newOrgId: string) {
    router.push(`/org/${newOrgId}`);
  }

  function switchProject(newProjectId: string) {
    const projectSection = pathname.match(
      /\/project\/[^/]+\/(.*)/
    );
    const section = projectSection?.[1] ?? "traces";
    router.push(`${orgBase}/project/${newProjectId}/${section}`);
  }

  const currentProjectName = resolvedProjectId
    ? projects.find((p) => p.id === resolvedProjectId)?.name
    : null;

  return (
    <Tooltip.Provider delayDuration={0}>
      <aside
        className={cn(
          "flex flex-col h-full bg-surface border-r border-border transition-all duration-200",
          collapsed ? "w-14" : "w-56"
        )}
      >
        <div className="flex items-center justify-between px-3 h-14 border-b border-border">
          {!collapsed && (
            <Link
              href={orgBase}
              className="text-sm font-mono text-primary tracking-tight"
            >
              PandaProbe
            </Link>
          )}
          <button
            onClick={toggleCollapsed}
            className="p-1 text-text-muted hover:text-text transition-colors"
          >
            {collapsed ? (
              <ChevronRight className="h-4 w-4" />
            ) : (
              <ChevronLeft className="h-4 w-4" />
            )}
          </button>
        </div>

        <nav className="flex-1 py-2 space-y-0.5 overflow-y-auto">
          <div className="space-y-0.5">
            {mainNav.map((item) => (
              <NavLink
                key={item.label}
                item={item}
                collapsed={collapsed}
                active={isActive(item)}
              />
            ))}
          </div>

          <div className="my-3 mx-3 border-t border-border" />

          {!collapsed && (
            <div className="px-3 pb-1">
              <span className="text-[10px] font-mono uppercase tracking-wider text-text-muted">
                Settings
              </span>
            </div>
          )}
          <div className="space-y-0.5">
            {settingsNav.map((item) => (
              <NavLink
                key={item.label}
                item={item}
                collapsed={collapsed}
                active={isActive(item)}
              />
            ))}
          </div>
        </nav>

        <div className="border-t border-border p-2 space-y-1">
          {!collapsed && organizations.length > 0 && (
            <DropdownMenu.Root>
              <DropdownMenu.Trigger className="flex w-full items-center justify-between px-2 py-1.5 text-xs font-mono text-text-dim hover:text-text hover:bg-surface-hi transition-colors">
                <span className="truncate">
                  {currentOrg?.name ?? "Select org"}
                </span>
                <ChevronsUpDown className="h-3 w-3 flex-shrink-0" />
              </DropdownMenu.Trigger>
              <DropdownMenu.Portal>
                <DropdownMenu.Content
                  side="top"
                  align="start"
                  className="z-50 min-w-[180px] bg-surface border border-border p-1 shadow-lg"
                >
                  {organizations.map((org) => (
                    <DropdownMenu.Item
                      key={org.id}
                      className={cn(
                        "flex items-center px-2 py-1.5 text-xs font-mono cursor-pointer outline-none",
                        org.id === currentOrg?.id
                          ? "text-primary bg-surface-hi"
                          : "text-text-dim hover:text-text hover:bg-surface-hi"
                      )}
                      onSelect={() => switchOrg(org.id)}
                    >
                      {org.name}
                    </DropdownMenu.Item>
                  ))}
                </DropdownMenu.Content>
              </DropdownMenu.Portal>
            </DropdownMenu.Root>
          )}

          {!collapsed && projects.length > 0 && (
            <DropdownMenu.Root>
              <DropdownMenu.Trigger className="flex w-full items-center justify-between px-2 py-1.5 text-xs font-mono text-text-dim hover:text-text hover:bg-surface-hi transition-colors">
                <span className="truncate">
                  {currentProjectName ?? "Select project"}
                </span>
                <ChevronsUpDown className="h-3 w-3 flex-shrink-0" />
              </DropdownMenu.Trigger>
              <DropdownMenu.Portal>
                <DropdownMenu.Content
                  side="top"
                  align="start"
                  className="z-50 min-w-[180px] bg-surface border border-border p-1 shadow-lg"
                >
                  {projects.map((proj) => (
                    <DropdownMenu.Item
                      key={proj.id}
                      className={cn(
                        "flex items-center px-2 py-1.5 text-xs font-mono cursor-pointer outline-none",
                        proj.id === resolvedProjectId
                          ? "text-primary bg-surface-hi"
                          : "text-text-dim hover:text-text hover:bg-surface-hi"
                      )}
                      onSelect={() => switchProject(proj.id)}
                    >
                      {proj.name}
                    </DropdownMenu.Item>
                  ))}
                </DropdownMenu.Content>
              </DropdownMenu.Portal>
            </DropdownMenu.Root>
          )}

          {authEnabled && user && (
            <button
              onClick={signOut}
              className={cn(
                "flex items-center gap-2 w-full px-2 py-1.5 text-xs font-mono text-text-muted hover:text-text hover:bg-surface-hi transition-colors",
                collapsed && "justify-center"
              )}
            >
              <LogOut className="h-3.5 w-3.5" />
              {!collapsed && <span>Sign out</span>}
            </button>
          )}
        </div>
      </aside>
    </Tooltip.Provider>
  );
}
