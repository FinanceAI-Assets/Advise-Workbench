"use client";

import { ChevronsUpDown, ShieldCheck, User } from "lucide-react";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";

import { cn } from "@/lib/utils";
import { useAuth } from "@/lib/auth-context";

export function WorkspaceSwitcher({ admin }: { admin: boolean }) {
  const { user } = useAuth();
  // The development server mirrors the backend's development-only admin override.
  // Production builds must rely on the server-provided capability.
  const developmentSwitchEnabled = process.env.NODE_ENV !== "production";
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!open) return;
    const closeOnOutsideClick = (event: MouseEvent) => {
      if (!containerRef.current?.contains(event.target as Node)) setOpen(false);
    };
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", closeOnOutsideClick);
    document.addEventListener("keydown", closeOnEscape);
    return () => {
      document.removeEventListener("mousedown", closeOnOutsideClick);
      document.removeEventListener("keydown", closeOnEscape);
    };
  }, [open]);

  const Icon = admin ? ShieldCheck : User;
  const currentLabel = admin ? "Admin console" : "User workspace";
  const destination = admin ? "/engagements" : "/admin/console";
  const destinationLabel = admin ? "User workspace" : "Admin console";
  const destinationIcon = admin ? User : ShieldCheck;
  const DestinationIcon = destinationIcon;

  return (
    <div ref={containerRef} className="relative">
      <button
        type="button"
        className="flex min-h-11 w-full items-center gap-2 rounded-md border border-[color:color-mix(in_srgb,var(--primary-700)_35%,transparent)] bg-[var(--primary-800)] px-3 py-2 text-sm font-semibold text-white"
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={() => setOpen((value) => !value)}
      >
        <Icon size={16} className="shrink-0 text-[var(--accent-green)]" />
        <span className="flex-1 text-left">{currentLabel}</span>
        <ChevronsUpDown size={14} className="shrink-0 text-[var(--primary-400)]" />
      </button>
      {open ? (
        <div
          className="absolute left-0 right-0 top-[calc(100%+6px)] z-50 rounded-md border border-[var(--surface-border)] bg-white p-1 shadow-lg"
          role="menu"
        >
          <div className="px-2 py-1 text-2xs font-semibold uppercase tracking-wide text-[var(--text-muted)]">
            Switch workspace
          </div>
          {admin || user?.canSwitchAdmin || developmentSwitchEnabled ? (
            <Link
              href={destination}
              role="menuitem"
              onClick={() => setOpen(false)}
              className={cn(
                "flex min-h-9 items-center gap-2 rounded px-2 text-xs font-medium !no-underline",
                "!text-[var(--text-default)] hover:bg-[var(--surface-muted)]"
              )}
            >
              <DestinationIcon size={15} className="text-[var(--accent-green-dark)]" />
              {destinationLabel}
            </Link>
          ) : (
            <p className="px-2 py-2 text-xs text-[var(--text-muted)]">No other workspaces available</p>
          )}
        </div>
      ) : null}
    </div>
  );
}
