"use client";

import { ChevronDown, Download } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { AdminStatCard, ControlsAuditPanel, IngestionHealthPanel, PendingApprovalsTable, RiskQueueTable } from "@/components/admin-console";
import { Button } from "@/components/ui/Button";
import { Skeleton } from "@/components/ui/Skeleton";
import { useAdminOverviewQuery } from "@/hooks/useAdminOverview";
import { useAuth } from "@/lib/auth-context";

export default function AdminConsoleOverviewPage() {
  const router = useRouter();
  const { token, ready } = useAuth();
  const [hydrated, setHydrated] = useState(false);

  const overview = useAdminOverviewQuery(Boolean(token));

  useEffect(() => {
    setHydrated(true);
  }, []);

  useEffect(() => {
    if (!ready) return;
    if (!token) router.replace("/login?next=/admin/console");
  }, [ready, token, router]);

  if (!hydrated || !ready || !token) {
    return (
      <main style={{ padding: 24 }}>
        <p>Redirecting…</p>
      </main>
    );
  }

  if (overview.isPending || !overview.data) {
    return (
      <main className="space-y-6">
        <Skeleton className="h-4 w-48" />
        <Skeleton className="h-9 w-96" />
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          {[0, 1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-28 w-full" />
          ))}
        </div>
      </main>
    );
  }

  const data = overview.data;

  return (
    <main className="space-y-6">
      <nav className="text-xs uppercase tracking-wide text-[var(--text-muted)]" aria-label="Breadcrumb">
        Admin console / Operations
      </nav>

      <header className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-[var(--text-default)]">Platform overview</h1>
          <p className="mt-1 text-sm text-[var(--text-muted)]">
            Operational oversight across the advisory workspace. Administrative rights do not grant access to engagement
            content.
          </p>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <Button variant="secondary" type="button" className="flex items-center gap-2 whitespace-nowrap">
            Last 7 days
            <ChevronDown size={16} aria-hidden />
          </Button>
          <Button variant="secondary" type="button" className="flex items-center gap-2 whitespace-nowrap">
            <Download size={16} aria-hidden />
            Export report
          </Button>
        </div>
      </header>

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        {data.stats.map((stat) => (
          <AdminStatCard key={stat.id} {...stat} />
        ))}
      </section>

      <div className="grid gap-4 lg:grid-cols-[1fr_380px]">
        <PendingApprovalsTable rows={data.pendingApprovals} total={data.pendingApprovalsTotal} />
        <IngestionHealthPanel items={data.ingestionHealth} updatedMeta={data.ingestionUpdatedMeta} warning={data.ingestionWarning} />
      </div>

      <div className="grid gap-4 lg:grid-cols-[1fr_380px]">
        <RiskQueueTable rows={data.riskQueue} openCount={data.riskQueueOpenCount} footnote={data.riskQueueFootnote} />
        <ControlsAuditPanel items={data.controlsAudit} auditEvent={data.controlsAuditEvent} />
      </div>
    </main>
  );
}
