"use client";

import { useEffect, useState, type ReactNode } from "react";
import { usePathname } from "next/navigation";

import { AdminSidebar } from "@/components/shell/AdminSidebar";
import { AppFooter } from "@/components/shell/AppFooter";
import { AdminTopbar } from "@/components/shell/AdminTopbar";

export function AdminShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const [hydrated, setHydrated] = useState(false);
  const [desktopNavCollapsed, setDesktopNavCollapsed] = useState(false);

  useEffect(() => {
    setDesktopNavCollapsed(
      window.localStorage.getItem("advise_workbench.adminDesktopNavCollapsed") === "true",
    );
    setHydrated(true);
  }, []);

  useEffect(() => {
    if (!hydrated) return;
    window.localStorage.setItem("advise_workbench.adminDesktopNavCollapsed", desktopNavCollapsed ? "true" : "false");
  }, [desktopNavCollapsed, hydrated]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setMobileNavOpen(false);
  }, [pathname]);

  useEffect(() => {
    if (!mobileNavOpen) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setMobileNavOpen(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [mobileNavOpen]);

  return (
    <div className="admin-console-shell flex min-h-screen bg-[var(--primary-50)] text-[var(--primary-900)]">
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:absolute focus:left-2 focus:top-2 focus:z-[100] focus:rounded focus:bg-white focus:px-4 focus:py-2 focus:text-sm focus:font-semibold focus:text-[var(--primary-900)] focus:shadow-lg focus:outline-2 focus:outline-[var(--accent-blue)]"
      >
        Skip to main content
      </a>
      <AdminSidebar
        mobileOpen={mobileNavOpen}
        onMobileClose={() => setMobileNavOpen(false)}
        desktopCollapsed={desktopNavCollapsed}
        onDesktopToggle={() => setDesktopNavCollapsed((prev) => !prev)}
      />
      <div className="app-shell-body relative z-[1] flex min-h-screen min-w-0 flex-1 flex-col">
        <AdminTopbar onMenuClick={() => setMobileNavOpen(true)} />
        {/* The main area fills the window height so the footer stays at the bottom on short pages. */}
        <main
          id="main-content"
          tabIndex={-1}
          className="admin-console-main mx-auto flex w-full max-w-[1400px] flex-1 flex-col p-4 md:p-6 outline-none"
        >
          <div className="flex-1">{children}</div>
          <AppFooter />
        </main>
      </div>
    </div>
  );
}
