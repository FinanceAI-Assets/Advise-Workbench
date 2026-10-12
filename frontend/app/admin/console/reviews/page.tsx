"use client";

import { Download, ShieldCheck } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import {
  AuditTrailPanel,
  PolicyControlsPanel,
  ReviewQueueTable,
  RoleAccessTable,
  SelectedReviewPanel,
} from "@/components/admin-console";
import { EngagementTabs } from "@/components/engagements";
import { Button } from "@/components/ui/Button";
import { EmptyState } from "@/components/ui/EmptyState";
import { Input } from "@/components/ui/Input";
import { Select } from "@/components/ui/Select";
import { Skeleton } from "@/components/ui/Skeleton";
import { useAdminReviewsGovernanceQuery } from "@/hooks/useAdminReviewsGovernance";
import { useAuth } from "@/lib/auth-context";

type GovernanceTabKey = "review-queue" | "risk-register" | "policies" | "access-roles" | "audit-trail";

export default function AdminConsoleReviewsPage() {
  const router = useRouter();
  const { token, ready } = useAuth();
  const [hydrated, setHydrated] = useState(false);
  const [tab, setTab] = useState<GovernanceTabKey>("review-queue");
  const [activeId, setActiveId] = useState<string | null>(null);

  const governance = useAdminReviewsGovernanceQuery(Boolean(token));

  useEffect(() => {
    setHydrated(true);
  }, []);

  useEffect(() => {
    if (!ready) return;
    if (!token) router.replace("/login?next=/admin/console/reviews");
  }, [ready, token, router]);

  if (!hydrated || !ready || !token) {
    return (
      <main style={{ padding: 24 }}>
        <p>Redirecting…</p>
      </main>
    );
  }

  if (governance.isPending || !governance.data) {
    return (
      <main className="space-y-6">
        <Skeleton className="h-4 w-48" />
        <Skeleton className="h-9 w-96" />
        <Skeleton className="h-64 w-full" />
      </main>
    );
  }

  const data = governance.data;
  const activeReviewId = activeId ?? data.selectedReview.id;
  const showingSelected = activeReviewId === data.selectedReview.id;

  const tabs = [
    { key: "review-queue" as const, label: "Review queue", count: data.tabCounts.reviewQueue },
    { key: "risk-register" as const, label: "Risk register", count: data.tabCounts.riskRegister },
    { key: "policies" as const, label: "Policies", count: data.tabCounts.policies },
    { key: "access-roles" as const, label: "Access roles" },
    { key: "audit-trail" as const, label: "Audit trail" },
  ];

  return (
    <main className="space-y-6">
      <nav className="text-xs uppercase tracking-wide text-[var(--text-muted)]" aria-label="Breadcrumb">
        Admin console / Reviews &amp; governance
      </nav>

      <header className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-[var(--text-default)]">Review operations &amp; governance</h1>
          <p className="mt-1 text-sm text-[var(--text-muted)]">
            Route approvals, resolve evidence risks and enforce the policy boundary between drafting, approval and export.
          </p>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <Button variant="secondary" type="button" className="flex items-center gap-2 whitespace-nowrap">
            <ShieldCheck size={16} aria-hidden />
            View policy set
          </Button>
          <Button variant="secondary" type="button" className="flex items-center gap-2 whitespace-nowrap">
            <Download size={16} aria-hidden />
            Export audit log
          </Button>
        </div>
      </header>

      <EngagementTabs tabs={tabs} active={tab} onChange={setTab} />

      {tab !== "review-queue" ? (
        <EmptyState
          title={`${tabs.find((t) => t.key === tab)?.label} view is coming soon`}
          description="This filtered view isn't wired up yet in this preview."
        />
      ) : (
        <>
          <div className="flex flex-wrap items-center gap-3">
            <Input placeholder="Search review or risk ID" className="min-w-[260px] flex-1" />
            <Select defaultValue="open" className="w-auto">
              <option value="open">State: Open</option>
              <option value="all">State: All</option>
            </Select>
          </div>

          <div className="grid gap-4 lg:grid-cols-[1fr_380px]">
            <ReviewQueueTable rows={data.queue} activeId={activeReviewId} onSelect={setActiveId} />
            {showingSelected ? (
              <SelectedReviewPanel review={data.selectedReview} />
            ) : (
              <div className="rounded-lg border border-[var(--surface-border)] bg-white p-6 text-sm text-[var(--text-muted)]">
                This review&apos;s detail isn&apos;t wired up yet in this demo.
              </div>
            )}
          </div>

          <div className="grid gap-4 lg:grid-cols-3">
            <PolicyControlsPanel
              items={data.policyControls}
              policyCode={data.policyCode}
              exportPermissionsNote={data.exportPermissionsNote}
            />
            <RoleAccessTable rows={data.roleAccess} />
            <AuditTrailPanel events={data.auditTrail} />
          </div>
        </>
      )}
    </main>
  );
}
