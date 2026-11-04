"use client";

import {
  Briefcase,
  ClipboardCheck,
  HelpCircle,
  Library,
  LayoutGrid,
  LogOut,
  ShieldCheck,
  Settings,
  PanelLeftClose,
  PanelLeftOpen,
  X,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef } from "react";

import { BrandMark } from "@/components/shell/BrandMark";
import { WorkspaceSwitcher } from "@/components/shell/WorkspaceSwitcher";
import { Button } from "@/components/ui/Button";
import { useAuth } from "@/lib/auth-context";
import { cn } from "@/lib/utils";

function NavLinkList({ onNavigate }: { onNavigate?: () => void }) {
  const pathname = usePathname();

  // Extract engagement ID from pathname if we're in an engagement context
  const engagementMatch = pathname.match(/^\/engagements\/([^/]+)/);
  const engagementId = engagementMatch?.[1];
  const isConversation = /\/conversation(\/|$)/.test(pathname);
  const isDeliverables = /\/deliverables(\/|$)/.test(pathname);

  // Navigation items - always clickable and visible. Each item owns its own
  // "active" test instead of a shared pathname.startsWith(href) check, since
  // "/engagements" is a literal prefix of every engagement sub-route — a
  // naive prefix match would keep "Engagements" highlighted at the same
  // time as "Conversation" or "Deliverables".
  const navLinks = [
    {
      href: "/engagements",
      label: "Engagements",
      icon: Briefcase,
      active: pathname === "/engagements" || (Boolean(engagementId) && !isConversation && !isDeliverables),
    },
    {
      href: "/library",
      label: "Leading Practice Library",
      icon: Library,
      active: pathname.startsWith("/library"),
    },
    {
      href: engagementId ? `/engagements/${engagementId}/conversation` : "/conversation",
      label: "Conversation",
      icon: LayoutGrid,
      active: isConversation,
    },
    { href: "/reviews", label: "Reviews", icon: ClipboardCheck, active: pathname.startsWith("/reviews") },
    {
      href: engagementId ? `/engagements/${engagementId}/deliverables` : "/deliverables",
      label: "Deliverables",
      icon: LayoutGrid,
      active: isDeliverables,
    },
    { href: "/skills", label: "Skills", icon: LayoutGrid, active: pathname.startsWith("/skills") },
  ];

  return (
    <>
      <p className="mb-1 px-2 text-2xs font-semibold uppercase tracking-wide text-[var(--primary-600)]">
        Workspace
      </p>
      {navLinks.map((item) => {
        const Icon = item.icon;

        return (
          <Link
            key={`${item.href}:${item.label}`}
            href={item.href}
            onClick={onNavigate}
            className={cn(
              "flex min-h-11 items-center gap-2 rounded-md border-l-2 px-2 py-2 text-sm transition !no-underline",
              item.active
                ? "border-l-[var(--accent-green)] bg-[var(--primary-800)] !text-white shadow-sm"
                : "border-l-transparent !text-[var(--primary-200)] hover:bg-[color:color-mix(in_srgb,var(--primary-800)_82%,black)] hover:!text-white"
            )}
          >
            <Icon size={18} />
            {item.label}
          </Link>
        );
      })}
    </>
  );
}

function userInitials(label: string): string {
  const parts = label.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return "?";
  return parts
    .slice(0, 2)
    .map((p) => p[0]?.toUpperCase())
    .join("");
}

function SidebarUserFooter({ onNavigate }: { onNavigate?: () => void }) {
  const { email, user, logout } = useAuth();
  const displayName = user?.name ?? email ?? "";

  return (
    <div className="space-y-1">
      {user?.isAdmin ? (
        <Link
          href="/admin/console"
          onClick={onNavigate}
          className="flex min-h-9 items-center gap-2 rounded-md px-2 text-sm !text-[#C0C8BC] !no-underline hover:bg-[color:color-mix(in_srgb,var(--primary-800)_82%,black)] hover:!text-white"
        >
          <ShieldCheck size={16} />
          Switch to admin console
        </Link>
      ) : null}
      <Link
        href="/help"
        onClick={onNavigate}
        className="flex min-h-9 items-center gap-2 rounded-md px-2 text-sm !text-[#C0C8BC] !no-underline hover:bg-[color:color-mix(in_srgb,var(--primary-800)_82%,black)] hover:!text-white"
      >
        <HelpCircle size={16} />
        Help &amp; documentation
      </Link>
      <Link
        href="/settings"
        onClick={onNavigate}
        className="flex min-h-9 items-center gap-2 rounded-md px-2 text-sm !text-[#C0C8BC] !no-underline hover:bg-[color:color-mix(in_srgb,var(--primary-800)_82%,black)] hover:!text-white"
      >
        <Settings size={16} />
        Settings
      </Link>
      <Link
        href="/profile"
        onClick={onNavigate}
        title="Your profile"
        className="mt-2 flex w-full items-center gap-2 rounded-md px-2 pt-2 text-left !no-underline hover:bg-[color:color-mix(in_srgb,var(--primary-800)_82%,black)]"
      >
        <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-[color:color-mix(in_srgb,var(--primary-800)_78%,black)] text-xs font-semibold text-[#FFFFFF]">
          {userInitials(displayName)}
        </span>
        <div className="min-w-0">
          <p className="truncate text-sm font-medium text-[#FFFFFF]">{displayName}</p>
          <p className="truncate text-xs text-[#A9B1A4]">{user?.jobTitle || "Workspace member"}</p>
        </div>
      </Link>
      <Button
        type="button"
        variant="ghost"
        onClick={() => {
          onNavigate?.();
          logout();
        }}
        className="flex min-h-9 w-full items-center gap-2 px-2 py-0 text-left font-normal text-[#C0C8BC] hover:bg-[color:color-mix(in_srgb,var(--primary-800)_82%,black)] hover:text-white"
      >
        <LogOut size={16} />
        Sign out
      </Button>
    </div>
  );
}

type ShellSidebarProps = {
  mobileOpen?: boolean;
  onMobileClose?: () => void;
  desktopCollapsed?: boolean;
  onDesktopToggle?: () => void;
};

export function ShellSidebar({
  mobileOpen = false,
  onMobileClose,
  desktopCollapsed = false,
  onDesktopToggle,
}: ShellSidebarProps) {
  const panelRef = useRef<HTMLDivElement | null>(null);
  const lastActiveElRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    if (!mobileOpen) {
      // Restore focus after closing the dialog.
      lastActiveElRef.current?.focus?.();
      return;
    }

    lastActiveElRef.current = document.activeElement as HTMLElement | null;

    const panel = panelRef.current;
    // Focus the first actionable element inside the dialog.
    const focusFirst = () => {
      const el = panel?.querySelector<HTMLElement>(
        'button,[href],input,select,textarea,[tabindex]:not([tabindex="-1"])'
      );
      el?.focus?.();
    };

    // Defer to ensure the panel is mounted and tabbable.
    const t = window.setTimeout(focusFirst, 0);

    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        onMobileClose?.();
        return;
      }

      if (e.key !== "Tab") return;
      if (!panel) return;

      const focusable = Array.from(
        panel.querySelectorAll<HTMLElement>('button,[href],input,select,textarea,[tabindex]:not([tabindex="-1"])')
      ).filter((node) => !node.hasAttribute("disabled") && node.tabIndex !== -1);

      if (focusable.length === 0) return;

      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      const active = document.activeElement as HTMLElement | null;

      if (e.shiftKey) {
        if (!active || active === first) {
          e.preventDefault();
          last.focus();
        }
      } else {
        if (active === last) {
          e.preventDefault();
          first.focus();
        }
      }
    };

    document.addEventListener("keydown", onKeyDown);
    return () => {
      window.clearTimeout(t);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [mobileOpen, onMobileClose]);

  return (
    <>
      <aside
        className={cn(
          "shell-sidebar sticky top-0 hidden h-screen shrink-0 flex-col border-r border-[color:color-mix(in_srgb,var(--primary-700)_35%,transparent)] bg-[var(--primary-950)] p-4 text-[#FFFFFF] transition-[width] lg:flex",
          desktopCollapsed ? "w-[72px]" : "w-[260px]"
        )}
      >
        <div className="mb-4 flex shrink-0 items-start justify-between gap-2 px-2">
          {desktopCollapsed ? (
            <span className="text-xs font-semibold text-[#C0C8BC]">AW</span>
          ) : (
            <BrandMark />
          )}
          <button
            type="button"
            className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md border border-[color:color-mix(in_srgb,var(--primary-700)_35%,transparent)] bg-[color:color-mix(in_srgb,var(--primary-800)_78%,black)] text-[#FFFFFF]"
            onClick={onDesktopToggle}
            aria-label={desktopCollapsed ? "Expand navigation" : "Collapse navigation"}
            aria-expanded={!desktopCollapsed}
          >
            {desktopCollapsed ? <PanelLeftOpen size={16} /> : <PanelLeftClose size={16} />}
          </button>
        </div>
        {/* Always show WorkspacePicker */}
        <div className="mb-6 shrink-0 px-0">
          <WorkspaceSwitcher admin={false} />
        </div>
        {/* Always show navigation items */}
        <nav className="shell-sidebar-nav flex-1 space-y-1">
          <NavLinkList />
        </nav>
        {/* Always show user footer */}
        <div className="mt-auto shrink-0 border-t border-[color:color-mix(in_srgb,var(--primary-700)_35%,transparent)] pt-3">
          <SidebarUserFooter />
        </div>
        {desktopCollapsed ? (
          <button
            type="button"
            className="absolute -right-3 top-4 flex h-7 w-7 items-center justify-center rounded-full border border-[color:color-mix(in_srgb,var(--primary-700)_35%,transparent)] bg-[var(--primary-900)] text-[#FFFFFF] shadow"
            onClick={onDesktopToggle}
            aria-label="Expand navigation"
            aria-expanded={false}
            title="Expand navigation"
          >
            <PanelLeftOpen size={14} />
          </button>
        ) : null}
      </aside>

      {/* Mobile drawer */}
      <div
        className={cn(
          "fixed inset-0 z-50 lg:hidden",
          mobileOpen ? "pointer-events-auto" : "pointer-events-none"
        )}
        aria-hidden={!mobileOpen}
      >
        <Button
          type="button"
          variant="ghost"
          className={cn(
            "absolute inset-0 rounded-none bg-black/40 p-0 hover:bg-black/40 transition-opacity motion-reduce:transition-none",
            mobileOpen ? "opacity-100" : "opacity-0"
          )}
          aria-label="Close navigation menu"
          onClick={onMobileClose}
        >
          <span className="sr-only">Close navigation menu</span>
        </Button>
        <div
          className={cn(
            "absolute left-0 top-0 flex h-full w-[min(280px,92vw)] flex-col border-r border-[color:color-mix(in_srgb,var(--primary-700)_35%,transparent)] bg-[var(--primary-950)] p-4 text-[#FFFFFF] shadow-xl transition-transform motion-reduce:transition-none",
            mobileOpen ? "translate-x-0" : "-translate-x-full"
          )}
          role="dialog"
          aria-modal="true"
          aria-labelledby="mobile-nav-title"
          ref={panelRef}
        >
          <div className="mb-4 flex shrink-0 items-center justify-between gap-2">
            <BrandMark id="mobile-nav-title" />
            <Button
              type="button"
              variant="ghost"
              className="flex h-11 w-11 items-center justify-center p-0 text-[#FFFFFF] hover:bg-[color:color-mix(in_srgb,var(--primary-800)_82%,black)] hover:text-[#FFFFFF] bg-transparent"
              onClick={onMobileClose}
              aria-label="Close menu"
            >
              <X size={20} className="text-[#FFFFFF]" />
            </Button>
          </div>
          <div className="mb-4 shrink-0">
            <WorkspaceSwitcher admin={false} />
          </div>
          <nav className="min-h-0 flex-1 space-y-1 overflow-y-auto">
            <NavLinkList onNavigate={onMobileClose} />
          </nav>
          <div className="mt-auto shrink-0 border-t border-[color:color-mix(in_srgb,var(--primary-700)_35%,transparent)] pt-3">
            <SidebarUserFooter onNavigate={onMobileClose} />
          </div>
        </div>
      </div>
    </>
  );
}
