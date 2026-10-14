"use client";

import { Bell, Menu, Search } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { useNotificationsQuery } from "@/hooks/useWorkbench";

type ShellTopbarProps = {
  onMenuClick?: () => void;
};

function useClock(): string {
  const [time, setTime] = useState("");
  useEffect(() => {
    const update = () =>
      setTime(new Date().toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" }));
    update();
    const id = window.setInterval(update, 30_000);
    return () => window.clearInterval(id);
  }, []);
  return time;
}

export function ShellTopbar({ onMenuClick }: ShellTopbarProps) {
  const time = useClock();
  const unread = useNotificationsQuery("unread").data?.counts.unread ?? 0;

  return (
    <header className="app-shell-topbar sticky top-0 z-40 flex h-14 items-center justify-between gap-3 border-b border-[color:color-mix(in_srgb,var(--primary-700)_20%,transparent)] bg-white/95 px-4 backdrop-blur">
      <div className="flex min-w-0 items-center gap-3">
        <button
          type="button"
          className="flex h-11 w-11 shrink-0 items-center justify-center rounded-md border border-[var(--surface-border)] bg-[var(--surface-muted)] text-[var(--text-default)] lg:hidden"
          onClick={onMenuClick}
          aria-label="Open navigation menu"
        >
          <Menu size={22} strokeWidth={2} aria-hidden />
        </button>
        <span className="truncate text-sm font-semibold text-[var(--text-default)]">Advisory / Transformation</span>
        <span className="hidden rounded-md bg-[var(--surface-muted)] px-2 py-0.5 text-2xs font-semibold uppercase tracking-wide text-[var(--text-muted)] sm:inline-flex">
          Sample workspace
        </span>
      </div>
      <form action="/search" role="search" className="relative hidden max-w-sm flex-1 sm:block">
        <Search
          size={14}
          className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-[var(--text-muted)]"
          aria-hidden
        />
        <input
          type="search"
          name="q"
          placeholder="Search workbench"
          className="w-full rounded-md border border-[var(--surface-border)] bg-white py-1.5 pl-8 pr-10 text-sm text-[var(--text-default)] outline-none ring-[var(--accent-blue)] focus:ring-2"
          aria-label="Search workbench"
        />
        <kbd className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-2xs text-[var(--text-muted)]">
          ⌘K
        </kbd>
      </form>
      <div className="flex shrink-0 items-center gap-3">
        <Link
          href="/notifications"
          className="relative flex h-9 w-9 items-center justify-center !text-[var(--text-muted)] hover:!text-[var(--text-default)]"
          aria-label={unread ? `Notifications, ${unread} unread` : "Notifications"}
        >
          <Bell size={18} aria-hidden />
          {unread ? (
            <span className="absolute right-0 top-0 flex h-4 min-w-4 items-center justify-center rounded-full bg-[var(--accent-green)] px-1 text-2xs font-semibold text-[var(--primary-950)]">
              {unread}
            </span>
          ) : null}
        </Link>
        <span className="hidden text-sm text-[var(--text-muted)] md:inline">{time}</span>
      </div>
    </header>
  );
}
