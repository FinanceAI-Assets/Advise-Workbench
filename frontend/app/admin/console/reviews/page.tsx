"use client";

import { useEffect, useState } from "react";

import {
  AuditTrailPanel,
  PolicyControlsPanel,
  ReviewQueueTable,
  RoleAccessTable,
  SelectedReviewPanel,
} from "@/components/admin-console";
import { EngagementTabs } from "@/components/engagements";
import { Card } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { Input } from "@/components/ui/Input";
import { Select } from "@/components/ui/Select";
import { ExportButton, ReasonAction, RecordsTable } from "@/components/workbench/AdminControls";
import { ErrorNote, PageFrame, PageSkeleton } from "@/components/workbench/PageFrame";
import { useAdminReviewsQuery } from "@/hooks/useAdminConsole";

type TabKey = "review-queue" | "risk-register" | "policies" | "access-roles" | "audit-trail";

export default function AdminConsoleReviewsPage() {
  const [tab, setTab] = useState<TabKey>("review-queue");
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState("");
  const [reviewerId, setReviewerId] = useState("");
  const governance = useAdminReviewsQuery(selected);

  // Links such as ?tab=audit open the audit trail.
  useEffect(() => {
    if (new URLSearchParams(window.location.search).get("tab") === "audit") setTab("audit-trail");
  }, []);

  if (governance.isPending && !governance.data) return <PageSkeleton />;
  const data = governance.data;
  if (!data) return <ErrorNote error={governance.error} />;

  const needle = query.trim().toLowerCase();
  const queue = data.queue.filter((row) => !needle || row.itemReference.toLowerCase().includes(needle));
  const current = data.selectedReview;
  const candidates = data.reviewers.filter((person) => person.id !== current?.ownerId);
  const chosen = reviewerId || candidates[0]?.id || "";

  const tabs = [
    { key: "review-queue" as const, label: "Review queue", count: data.tabCounts.reviewQueue },
    { key: "risk-register" as const, label: "Risk register", count: data.tabCounts.riskRegister },
    { key: "policies" as const, label: "Policies", count: data.tabCounts.policies },
    { key: "access-roles" as const, label: "Access roles" },
    { key: "audit-trail" as const, label: "Audit trail" },
  ];

  return (
    <PageFrame
      breadcrumb="Admin console / Reviews & governance"
      title="Review operations & governance"
      subtitle="Route approvals, resolve evidence risks and enforce the policy boundary between drafting, approval and export."
      actions={<ExportButton report="audit" label="Export audit log" />}
    >
      <EngagementTabs tabs={tabs} active={tab} onChange={setTab} />

      {tab === "review-queue" ? (
        <>
          <Input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search review or item" />
          {queue.length === 0 ? (
            <EmptyState title="No open reviews" description="Every submitted artifact has been decided." />
          ) : (
            <div className="grid gap-4 lg:grid-cols-[1fr_380px]">
              <ReviewQueueTable rows={queue} activeId={current?.id ?? ""} onSelect={setSelected} />
              {current ? (
                <SelectedReviewPanel
                  review={current}
                  actions={
                    <ReasonAction
                      primary
                      label="Assign reviewer"
                      build={(reason) => ({ path: `/reviews/${current.id}/assign`, body: { reviewerId: chosen, reason } })}
                    >
                      <Select aria-label="Independent reviewer" value={chosen} onChange={(e) => setReviewerId(e.target.value)}>
                        {candidates.map((person) => (
                          <option key={person.id} value={person.id}>
                            {person.name}
                          </option>
                        ))}
                      </Select>
                    </ReasonAction>
                  }
                />
              ) : null}
            </div>
          )}
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
      ) : null}

      {tab === "risk-register" ? (
        <RecordsTable
          title="Risk register"
          columns={[
            ["riskScope", "Risk / scope"],
            ["severity", "Severity"],
            ["owner", "Owner"],
            ["control", "Control"],
          ]}
          rows={data.risks}
          empty="No open risks."
        />
      ) : null}

      {tab === "policies" ? (
        <PolicyControlsPanel
          items={data.policyControls}
          policyCode={data.policyCode}
          exportPermissionsNote={data.exportPermissionsNote}
        />
      ) : null}

      {tab === "access-roles" ? <RoleAccessTable rows={data.roleAccess} /> : null}

      {tab === "audit-trail" ? (
        <Card className="space-y-3">
          <h2 className="text-base font-semibold text-[var(--text-default)]">Audit trail · Newest first</h2>
          {data.fullAuditTrail.length === 0 ? (
            <p className="text-sm text-[var(--text-muted)]">No events recorded yet.</p>
          ) : (
            <ul className="divide-y divide-[var(--surface-border)]">
              {data.fullAuditTrail.map((event) => (
                <li key={event.id} className="py-2">
                  <p className="text-sm font-medium text-[var(--text-default)]">{event.title}</p>
                  <p className="text-xs text-[var(--text-muted)]">{event.attribution}</p>
                </li>
              ))}
            </ul>
          )}
          <p className="text-xs text-[var(--text-muted)]">
            Append-only. Policy changes and role assignments record a reason, a named owner and a timestamp.
          </p>
        </Card>
      ) : null}
    </PageFrame>
  );
}
