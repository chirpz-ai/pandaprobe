"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
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
import { useProject } from "@/components/providers/ProjectProvider";
import * as Tooltip from "@radix-ui/react-tooltip";
import * as DropdownMenu from "@radix-ui/react-dropdown-menu";

const STORAGE_KEY = "pandaprobe_sidebar_collapsed";

interface NavItem {
  label: string;
  href: string;
  icon: React.ReactNode;
}

const mainNav: NavItem[] = [
  { label: "Dashboard", href: "/dashboard", icon: <LayoutDashboard className="h-4 w-4" /> },
  { label: "Traces", href: "/dashboard/traces", icon: <ListTree className="h-4 w-4" /> },
  { label: "Sessions", href: "/dashboard/sessions", icon: <Layers className="h-4 w-4" /> },
  { label: "Evaluations", href: "/dashboard/evaluations", icon: <CheckCircle className="h-4 w-4" /> },
  { label: "Analytics", href: "/dashboard/analytics", icon: <BarChart3 className="h-4 w-4" /> },
];

const settingsNav: NavItem[] = [
  { label: "Organization", href: "/dashboard/settings/organization", icon: <Building2 className="h-4 w-4" /> },
  { label: "Members", href: "/dashboard/settings/members", icon: <Users className="h-4 w-4" /> },
  { label: "Projects", href: "/dashboard/settings/projects", icon: <FolderKanban className="h-4 w-4" /> },
  { label: "API Keys", href: "/dashboard/settings/api-keys", icon: <KeyRound className="h-4 w-4" /> },
  { label: "Billing", href: "/dashboard/settings/billing", icon: <CreditCard className="h-4 w-4" /> },
];

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
  const { signOut, authEnabled, user } = useAuth();
  const { organizations, currentOrg, setCurrentOrg } = useOrganization();
  const { projects, currentProject, setCurrentProject } = useProject();
  const [collapsed, setCollapsed] = useState(() => {
    if (typeof window === "undefined") return false;
    return localStorage.getItem(STORAGE_KEY) === "true";
  });

  function toggleCollapsed() {
    const next = !collapsed;
    setCollapsed(next);
    localStorage.setItem(STORAGE_KEY, String(next));
  }

  return (
    <Tooltip.Provider delayDuration={0}>
      <aside
        className={cn(
          "flex flex-col h-full bg-surface border-r border-border transition-all duration-200",
          collapsed ? "w-14" : "w-56"
        )}
      >
        {/* Logo */}
        <div className="flex items-center justify-between px-3 h-14 border-b border-border">
          {!collapsed && (
            <Link href="/dashboard" className="text-sm font-mono text-primary tracking-tight">
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

        {/* Main nav */}
        <nav className="flex-1 py-2 space-y-0.5 overflow-y-auto">
          <div className="space-y-0.5">
            {mainNav.map((item) => (
              <NavLink
                key={item.href}
                item={item}
                collapsed={collapsed}
                active={pathname === item.href}
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
                key={item.href}
                item={item}
                collapsed={collapsed}
                active={pathname === item.href}
              />
            ))}
          </div>
        </nav>

        {/* Footer: switchers + user */}
        <div className="border-t border-border p-2 space-y-1">
          {/* Org Switcher */}
          {!collapsed && organizations.length > 0 && (
            <DropdownMenu.Root>
              <DropdownMenu.Trigger className="flex w-full items-center justify-between px-2 py-1.5 text-xs font-mono text-text-dim hover:text-text hover:bg-surface-hi transition-colors">
                <span className="truncate">{currentOrg?.name ?? "Select org"}</span>
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
                      onSelect={() => setCurrentOrg(org)}
                    >
                      {org.name}
                    </DropdownMenu.Item>
                  ))}
                </DropdownMenu.Content>
              </DropdownMenu.Portal>
            </DropdownMenu.Root>
          )}

          {/* Project Switcher */}
          {!collapsed && projects.length > 0 && (
            <DropdownMenu.Root>
              <DropdownMenu.Trigger className="flex w-full items-center justify-between px-2 py-1.5 text-xs font-mono text-text-dim hover:text-text hover:bg-surface-hi transition-colors">
                <span className="truncate">{currentProject?.name ?? "Select project"}</span>
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
                        proj.id === currentProject?.id
                          ? "text-primary bg-surface-hi"
                          : "text-text-dim hover:text-text hover:bg-surface-hi"
                      )}
                      onSelect={() => setCurrentProject(proj)}
                    >
                      {proj.name}
                    </DropdownMenu.Item>
                  ))}
                </DropdownMenu.Content>
              </DropdownMenu.Portal>
            </DropdownMenu.Root>
          )}

          {/* Sign out */}
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
