"use client";

import { useEffect, useMemo, useState } from "react";
import Image from "next/image";
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
  ArrowLeft,
  Settings,
  SlidersHorizontal,
  LogOut,
  Book,
  Bug,
  ChevronsUpDown,
  CircleUser,
  Plus,
} from "lucide-react";
import { cn } from "@/lib/utils/cn";
import { useAuth } from "@/components/providers/AuthProvider";
import { useOrganization } from "@/components/providers/OrganizationProvider";
import { useOrgId, useResolvedProjectId } from "@/hooks/useNavigation";
import { createOrganization } from "@/lib/api/organizations";
import { extractErrorMessage } from "@/lib/api/client";
import { useToast } from "@/components/providers/ToastProvider";
import { FormDialog } from "@/components/common/FormDialog";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
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
        collapsed && "justify-center px-2",
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

function SwitcherDropdown({
  label,
  icon,
  items,
  activeId,
  onSelect,
  collapsed,
  side = "right",
  footerAction,
}: {
  label: string;
  icon: React.ReactNode;
  items: { id: string; name: string }[];
  activeId: string | null;
  onSelect: (id: string) => void;
  collapsed: boolean;
  side?: "right" | "bottom";
  footerAction?: { label: string; icon: React.ReactNode; onSelect: () => void };
}) {
  const trigger = (
    <DropdownMenu.Trigger
      className={cn(
        "flex w-full items-center gap-3 px-3 py-2 text-sm font-mono transition-colors duration-150",
        "text-text hover:bg-surface-hi",
        collapsed && "justify-center px-2",
      )}
    >
      {icon}
      {!collapsed && (
        <>
          <span className="flex-1 truncate text-left">{label}</span>
          <ChevronsUpDown className="h-4 w-4 flex-shrink-0 text-text-muted" />
        </>
      )}
    </DropdownMenu.Trigger>
  );

  return (
    <DropdownMenu.Root>
      {collapsed ? (
        <Tooltip.Root>
          <Tooltip.Trigger asChild>{trigger}</Tooltip.Trigger>
          <Tooltip.Portal>
            <Tooltip.Content
              side="right"
              sideOffset={8}
              className="z-50 bg-surface border border-border px-2 py-1 text-xs font-mono text-text"
            >
              {label}
            </Tooltip.Content>
          </Tooltip.Portal>
        </Tooltip.Root>
      ) : (
        trigger
      )}
      <DropdownMenu.Portal>
        <DropdownMenu.Content
          side={side}
          align="start"
          sideOffset={side === "right" ? 8 : 4}
          className="z-50 min-w-[200px] max-h-[300px] overflow-y-auto bg-surface border border-border p-1 shadow-lg"
        >
          {items.map((item) => (
            <DropdownMenu.Item
              key={item.id}
              className={cn(
                "flex items-center px-2 py-1.5 text-xs font-mono cursor-pointer outline-none",
                item.id === activeId
                  ? "text-primary bg-surface-hi"
                  : "text-text-dim hover:text-text hover:bg-surface-hi",
              )}
              onSelect={() => onSelect(item.id)}
            >
              {item.name}
            </DropdownMenu.Item>
          ))}
          {footerAction && (
            <>
              <DropdownMenu.Separator className="my-1 mx-1 border-t border-border" />
              <DropdownMenu.Item
                className="flex items-center gap-2 px-2 py-1.5 text-xs font-mono text-text-muted hover:text-text hover:bg-surface-hi cursor-pointer outline-none"
                onSelect={footerAction.onSelect}
              >
                {footerAction.icon}
                {footerAction.label}
              </DropdownMenu.Item>
            </>
          )}
        </DropdownMenu.Content>
      </DropdownMenu.Portal>
    </DropdownMenu.Root>
  );
}

export function Sidebar() {
  const pathname = usePathname();
  const router = useRouter();
  const { signOut, authEnabled, user } = useAuth();
  const { organizations, currentOrg, projects, refetchOrgs } =
    useOrganization();
  const { toast } = useToast();
  const orgId = useOrgId();
  const resolvedProjectId = useResolvedProjectId(projects);

  const [collapsed, setCollapsed] = useState(false);
  const [createOrgOpen, setCreateOrgOpen] = useState(false);
  const [newOrgName, setNewOrgName] = useState("");

  const inSettingsRoute = pathname.includes("/settings");
  const [settingsView, setSettingsView] = useState(inSettingsRoute);

  useEffect(() => {
    setSettingsView(inSettingsRoute);
  }, [inSettingsRoute]);

  useEffect(() => {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored === "true") setCollapsed(true);
  }, []);

  const orgBase = `/org/${orgId}`;
  const projectBase = resolvedProjectId
    ? `${orgBase}/project/${resolvedProjectId}`
    : null;

  const projectHome = projectBase ?? orgBase;

  const projectNav = useMemo<NavItem[]>(
    () => [
      {
        label: "Home",
        href: projectHome,
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
    [orgBase, projectBase, projectHome],
  );

  const settingsNav = useMemo<NavItem[]>(
    () => [
      {
        label: "Organization",
        href: `${orgBase}/settings/organization`,
        icon: <SlidersHorizontal className="h-4 w-4" />,
      },
      {
        label: "Members",
        href: `${orgBase}/settings/members`,
        icon: <Users className="h-4 w-4" />,
      },
      {
        label: "Projects",
        href: `${orgBase}/settings/projects`,
        icon: <FolderKanban className="h-4 w-4" />,
      },
      {
        label: "API Keys",
        href: `${orgBase}/settings/api-keys`,
        icon: <KeyRound className="h-4 w-4" />,
      },
      {
        label: "Billing",
        href: `${orgBase}/settings/billing`,
        icon: <CreditCard className="h-4 w-4" />,
      },
    ],
    [orgBase],
  );

  function isActive(item: NavItem): boolean {
    if (item.exact) return pathname === item.href;
    return (
      pathname.startsWith(item.href) &&
      item.href !== orgBase &&
      item.href !== projectHome
    );
  }

  function toggleCollapsed() {
    const next = !collapsed;
    setCollapsed(next);
    localStorage.setItem(STORAGE_KEY, String(next));
  }

  function openSettings() {
    setSettingsView(true);
    router.push(`${orgBase}/settings/organization`);
  }

  function exitSettings() {
    setSettingsView(false);
    router.push(projectHome);
  }

  function switchOrg(newOrgId: string) {
    router.push(`/org/${newOrgId}/settings/organization`);
  }

  function switchProject(newProjectId: string) {
    const projectSection = pathname.match(/\/project\/[^/]+\/(.*)/);
    const section = projectSection?.[1];
    const target = section
      ? `${orgBase}/project/${newProjectId}/${section}`
      : `${orgBase}/project/${newProjectId}`;
    router.push(target);
  }

  async function handleCreateOrg() {
    if (!newOrgName.trim()) return;
    try {
      const org = await createOrganization({ name: newOrgName.trim() });
      toast({ title: "Organization created", variant: "success" });
      setNewOrgName("");
      refetchOrgs();
      router.push(`/org/${org.id}/settings/organization`);
    } catch (err) {
      toast({ title: extractErrorMessage(err), variant: "error" });
      throw err;
    }
  }

  const currentProjectName = resolvedProjectId
    ? projects.find((p) => p.id === resolvedProjectId)?.name
    : null;

  const displayName = user?.displayName || user?.email?.split("@")[0] || "User";
  const displayEmail = user?.email || "";

  return (
    <Tooltip.Provider delayDuration={0}>
      <aside
        className={cn(
          "flex flex-col h-full bg-surface border-r border-border transition-all duration-200",
          collapsed ? "w-14" : "w-56",
        )}
      >
        {/* ── Header (h-12 to match TopBar) ──────────────────────── */}
        <div className="flex items-center justify-between px-3 h-12 border-b border-border">
          {!collapsed && settingsView ? (
            <button
              onClick={exitSettings}
              className="flex items-center gap-2 text-sm font-mono text-primary tracking-tight hover:text-text transition-colors"
            >
              <Image
                src="/favicon-32x32.png"
                alt=""
                width={18}
                height={18}
                className="flex-shrink-0"
              />
              <span>PandaProbe</span>
            </button>
          ) : !collapsed ? (
            <Link
              href={projectHome}
              className="flex items-center gap-2 text-sm font-mono text-primary tracking-tight"
            >
              <Image
                src="/favicon-32x32.png"
                alt=""
                width={18}
                height={18}
                className="flex-shrink-0"
              />
              PandaProbe
            </Link>
          ) : null}
          <button
            onClick={toggleCollapsed}
            className={`${collapsed ? "p-2" : "p-0"} text-text-muted hover:text-text transition-colors`}
          >
            {collapsed ? (
              <ChevronRight className="h-4 w-4" />
            ) : (
              <ChevronLeft className="h-4 w-4" />
            )}
          </button>
        </div>

        {/* ── Navigation ─────────────────────────────────────────── */}
        <nav className="flex-1 py-2 overflow-y-auto">
          {settingsView ? (
            <>
              {/* Org switcher at top of settings view */}
              <SwitcherDropdown
                label={currentOrg?.name ?? "Select org"}
                icon={<Building2 className="h-4 w-4" />}
                items={organizations.map((o) => ({ id: o.id, name: o.name }))}
                activeId={currentOrg?.id ?? null}
                onSelect={switchOrg}
                collapsed={collapsed}
                footerAction={{
                  label: "New Organization",
                  icon: <Plus className="h-3.5 w-3.5" />,
                  onSelect: () => setCreateOrgOpen(true),
                }}
              />

              <div className="space-y-0.5 mt-1">
                {settingsNav.map((item) => (
                  <NavLink
                    key={item.label}
                    item={item}
                    collapsed={collapsed}
                    active={isActive(item)}
                  />
                ))}
              </div>
            </>
          ) : (
            <>
              {/* Project switcher at top of main view */}
              {projects.length > 0 ? (
                <SwitcherDropdown
                  label={currentProjectName ?? "Select project"}
                  icon={<FolderKanban className="h-4 w-4" />}
                  items={projects.map((p) => ({ id: p.id, name: p.name }))}
                  activeId={resolvedProjectId}
                  onSelect={switchProject}
                  collapsed={collapsed}
                />
              ) : !collapsed ? (
                <div className="px-3 py-2 text-xs font-mono text-text-muted">
                  No projects yet
                </div>
              ) : null}

              <div className="space-y-0.5 mt-1">
                {projectNav.map((item) => (
                  <NavLink
                    key={item.label}
                    item={item}
                    collapsed={collapsed}
                    active={isActive(item)}
                  />
                ))}
              </div>
            </>
          )}
        </nav>

        {/* ── Settings / Back button (above divider) ──────────────── */}
        <div className="pb-2">
          <Tooltip.Root>
            <Tooltip.Trigger asChild>
              {settingsView ? (
                <Button
                  variant="ghost"
                  onClick={exitSettings}
                  className={cn(
                    "w-full justify-start gap-3 px-3 py-2",
                    collapsed && "justify-center px-2",
                  )}
                >
                  <ArrowLeft className="h-4 w-4" />
                  {!collapsed && <span>Back to Home</span>}
                </Button>
              ) : (
                <Button
                  variant="ghost"
                  onClick={openSettings}
                  className={cn(
                    "w-full justify-start gap-3 px-3 py-2",
                    collapsed && "justify-center px-2",
                  )}
                >
                  <Settings className="h-4 w-4" />
                  {!collapsed && <span>Settings</span>}
                </Button>
              )}
            </Tooltip.Trigger>
            {collapsed && (
              <Tooltip.Portal>
                <Tooltip.Content
                  side="right"
                  sideOffset={8}
                  className="z-50 bg-surface border border-border px-2 py-1 text-xs font-mono text-text"
                >
                  {settingsView ? "Back to Home" : "Settings"}
                </Tooltip.Content>
              </Tooltip.Portal>
            )}
          </Tooltip.Root>
        </div>

        {/* ── Footer ─────────────────────────────────────────────── */}
        <div className="border-t border-border py-2">
          {/* User menu */}
          {authEnabled && user ? (
            <DropdownMenu.Root>
              <DropdownMenu.Trigger
                className={cn(
                  "flex items-center gap-2 w-full px-3 py-2 text-xs font-mono text-text-dim hover:text-text hover:bg-surface-hi transition-colors",
                  collapsed && "justify-center px-2",
                )}
              >
                <CircleUser className="h-4 w-4 flex-shrink-0" />
                {!collapsed && <span className="truncate">{displayName}</span>}
              </DropdownMenu.Trigger>
              <DropdownMenu.Portal>
                <DropdownMenu.Content
                  side="top"
                  align="center"
                  sideOffset={8}
                  className="z-50 w-[calc(14rem-16px)] bg-surface border border-border p-1 shadow-lg"
                >
                  <div className="px-2 py-2 border-b border-border mb-1">
                    <p className="text-xs font-mono text-text truncate">
                      {displayName}
                    </p>
                    <p className="text-[10px] font-mono text-text-muted truncate">
                      {displayEmail}
                    </p>
                  </div>
                  <DropdownMenu.Item
                    className="flex items-center gap-2 px-2 py-1.5 text-xs font-mono text-text-dim hover:text-text hover:bg-surface-hi cursor-pointer outline-none"
                    onSelect={() =>
                      window.open("https://docs.pandaprobe.com", "_blank")
                    }
                  >
                    <Book className="h-3.5 w-3.5" />
                    Documentation
                  </DropdownMenu.Item>
                  <DropdownMenu.Item
                    className="flex items-center gap-2 px-2 py-1.5 text-xs font-mono text-text-dim hover:text-text hover:bg-surface-hi cursor-pointer outline-none"
                    onSelect={() =>
                      window.open("mailto:support@chirpz.ai", "_blank")
                    }
                  >
                    <Bug className="h-3.5 w-3.5" />
                    Report a bug
                  </DropdownMenu.Item>
                  <DropdownMenu.Separator className="my-1 mx-1 border-t border-border" />
                  <DropdownMenu.Item
                    className="flex items-center gap-2 px-2 py-1.5 text-xs font-mono text-text-dim hover:text-text hover:bg-surface-hi cursor-pointer outline-none"
                    onSelect={() => signOut()}
                  >
                    <LogOut className="h-3.5 w-3.5" />
                    Sign out
                  </DropdownMenu.Item>
                </DropdownMenu.Content>
              </DropdownMenu.Portal>
            </DropdownMenu.Root>
          ) : !authEnabled ? (
            <div
              className={cn(
                "flex items-center gap-2 px-3 py-2 text-xs font-mono text-text-muted",
                collapsed && "justify-center px-2",
              )}
            >
              <CircleUser className="h-4 w-4 flex-shrink-0" />
              {!collapsed && <span>Dev User</span>}
            </div>
          ) : null}
        </div>
      </aside>

      <FormDialog
        open={createOrgOpen}
        onOpenChange={(v) => {
          setCreateOrgOpen(v);
          if (!v) setNewOrgName("");
        }}
        title="Create Organization"
        description="Organizations are isolated workspaces for your projects, traces, and team members. You can own up to 2 organizations."
        submitLabel="Create"
        submitDisabled={!newOrgName.trim()}
        onSubmit={handleCreateOrg}
      >
        <div>
          <label className="text-xs font-mono text-text-muted block mb-1">
            Organization Name
          </label>
          <Input
            value={newOrgName}
            onChange={(e) => setNewOrgName(e.target.value)}
            placeholder="My Organization"
            onKeyDown={(e) => {
              if (e.key === "Enter" && newOrgName.trim()) handleCreateOrg();
            }}
            autoFocus
          />
        </div>
      </FormDialog>
    </Tooltip.Provider>
  );
}
