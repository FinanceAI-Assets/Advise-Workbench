"use client";

import { Download } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { AdminEngagementsTable, DeliverableLifecyclePanel, SelectedEngagementPanel } from "@/components/admin-console";
import { EngagementTabs } from "@/components/engagements";
import { Button } from "@/components/ui/Button";
import { EmptyState } from "@/components/ui/EmptyState";
import { Input } from "@/components/ui/Input";
import { Select } from "@/components/ui/Select";
import { Skeleton } from "@/components/ui/Skeleton";
import { useAdminEngagementsQuery } from "@/hooks/useAdminEngagements";
import { useAuth } from "@/lib/auth-context";

type AdminEngagementsTabKey = "engagements" | "deliverables" | "retention-exceptions" | "export-requests";

export default function AdminConsoleEngagementsPage() {
  const router = useRouter();
  const { token, ready } = useAuth();
  const [hydrated, setHydrated] = useState(false);
  const [tab, setTab] = useState<AdminEngagementsTabKey>("engagements");
  const [activeId, setActiveId] = useState<string | null>(null);

  const engagements = useAdminEngagementsQuery(Boolean(token));

  useEffect(() => {
    setHydrated(true);
  }, []);

  useEffect(() => {
    if (!ready) return;
    if (!token) router.replace("/login?next=/admin/console/engagements");
  }, [ready, token, router]);

  if (!hydrated || !ready || !token) {
    return (
      <main style={{ padding: 24 }}>
        <p>Redirecting…</p>
      </main>
    );
  }

  if (engagements.isPending || !engagements.data) {
    return (
      <main className="space-y-6">
        <Skeleton className="h-4 w-48" />
        <Skeleton className="h-9 w-96" />
        <Skeleton className="h-64 w-full" />
      </main>
    );
  }

  const data = engagements.data;
  const activeEngagementId = activeId ?? data.selected.id;
  const showingSelected = activeEngagementId === data.selected.id;

  const tabs = [
    { key: "engagements" as const, label: "Engagements", count: data.tabCounts.engagements },
    { key: "deliverables" as const, label: "Deliverables", count: data.tabCounts.deliverables },
    { key: "retention-exceptions" as const, label: "Retention exceptions", count: data.tabCounts.retentionExceptions },
    { key: "export-requests" as const, label: "Export requests", count: data.tabCounts.exportRequests },
  ];

  return (
    <main className="space-y-6">
      <nav className="text-xs uppercase tracking-wide text-[var(--text-muted)]" aria-label="Breadcrumb">
        Admin console / Engagements &amp; deliverables
      </nav>

      <header className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-[var(--text-default)]">Engagement oversight</h1>
          <p className="mt-1 text-sm text-[var(--text-muted)]">
            Manage ownership, access and lifecycle controls. Content and artifact approvals remain with assigned engagement
            reviewers.
          </p>
        </div>
        <Button variant="secondary" type="button" className="flex shrink-0 items-center gap-2 whitespace-nowrap">
          <Download size={16} aria-hidden />
          Export inventory
        </Button>
      </header>

      <EngagementTabs tabs={tabs} active={tab} onChange={setTab} />

      {tab !== "engagements" ? (
        <EmptyState
          title={`${tabs.find((t) => t.key === tab)?.label} view is coming soon`}
          description="This filtered view isn't wired up yet in this preview."
        />
      ) : (
        <>
          <div className="flex flex-wrap items-center gap-3">
            <Input placeholder="Search engagement, owner or ID" className="min-w-[260px] flex-1" />
            <Select defaultValue="all" className="w-auto">
              <option value="all">Classification: All</option>
              <option value="internal">Classification: Internal</option>
              <option value="restricted">Classification: Restricted</option>
            </Select>
            <Button variant="secondary" type="button" className="whitespace-nowrap">
              Lifecycle: Active
            </Button>
            <span className="ml-auto text-xs text-[var(--text-muted)]">
              {data.matchingCount} of {data.totalCount} engagements
            </span>
          </div>

          <AdminEngagementsTable rows={data.rows} activeId={activeEngagementId} onSelect={setActiveId} />

          <div className="grid gap-4 lg:grid-cols-2">
            {showingSelected ? (
              <SelectedEngagementPanel engagement={data.selected} />
            ) : (
              <div className="rounded-lg border border-[var(--surface-border)] bg-white p-6 text-sm text-[var(--text-muted)]">
                This engagement&apos;s detail isn&apos;t wired up yet in this demo.
              </div>
            )}
            <DeliverableLifecyclePanel items={data.deliverableLifecycle} />
          </div>
        </>
      )}
    </main>
  );
}
