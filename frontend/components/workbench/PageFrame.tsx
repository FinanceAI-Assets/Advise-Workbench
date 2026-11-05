import type { ReactNode } from "react";

import { Skeleton } from "@/components/ui/Skeleton";

/** Standard workbench page layout: breadcrumb, title row with actions, content, and the sample-content footer. */
export function PageFrame({
  breadcrumb,
  title,
  subtitle,
  actions,
  children,
}: {
  breadcrumb: ReactNode;
  title: string;
  subtitle?: ReactNode;
  actions?: ReactNode;
  children: ReactNode;
}) {
  return (
    <main className="space-y-6">
      <nav className="text-xs uppercase tracking-wide text-[var(--text-muted)]" aria-label="Breadcrumb">
        {breadcrumb}
      </nav>
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-[var(--text-default)]">{title}</h1>
          {subtitle ? <p className="mt-1 text-sm text-[var(--text-muted)]">{subtitle}</p> : null}
        </div>
        {actions ? <div className="flex shrink-0 flex-wrap items-center gap-2">{actions}</div> : null}
      </header>
      {children}
      <footer className="flex flex-wrap items-center justify-between gap-2 border-t border-[var(--surface-border)] pt-4 text-xs text-[var(--text-muted)]">
        <span>Illustrative content only · No real client or confidential information</span>
        <span>Advise Workbench · Secure advisory environment</span>
      </footer>
    </main>
  );
}

export function PageSkeleton() {
  return (
    <main className="space-y-6" aria-busy>
      <Skeleton className="h-4 w-40" />
      <Skeleton className="h-9 w-80" />
      <Skeleton className="h-24 w-full" />
      <Skeleton className="h-64 w-full" />
    </main>
  );
}

/** Label above a value, as used in the design's detail panels. */
export function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div>
      <p className="text-2xs font-semibold uppercase tracking-wide text-[var(--text-muted)]">{label}</p>
      <div className="mt-1 text-sm text-[var(--text-default)]">{children}</div>
    </div>
  );
}

export function ErrorNote({ error }: { error: unknown }) {
  if (!error) return null;
  return (
    <p role="alert" className="rounded-md border border-[#E8B4AE] bg-[#FBEFEB] px-3 py-2 text-sm text-[#A53E37]">
      {error instanceof Error ? error.message : "Something went wrong."}
    </p>
  );
}
