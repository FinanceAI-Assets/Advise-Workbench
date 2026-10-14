"use client";

import Link from "next/link";
import { useState } from "react";

import { AdminEngagementsTable, DeliverableLifecyclePanel, SelectedEngagementPanel } from "@/components/admin-console";
import { EngagementTabs } from "@/components/engagements";
import { Input } from "@/components/ui/Input";
import { Select } from "@/components/ui/Select";
import { ExportButton, ReasonAction, RecordsTable } from "@/components/workbench/AdminControls";
import { ErrorNote, PageFrame, PageSkeleton } from "@/components/workbench/PageFrame";
import { useAdminEngagementsQuery } from "@/hooks/useAdminConsole";

type TabKey = "engagements" | "deliverables" | "retention-exceptions" | "export-requests";

export default function AdminConsoleEngagementsPage() {
  const [tab, setTab] = useState<TabKey>("engagements");
  const [query, setQuery] = useState("");
  const [classification, setClassification] = useState("all");
  const [selected, setSelected] = useState("");
  const [days, setDays] = useState("365");
  const [email, setEmail] = useState("");
  const [role, setRole] = useState("Contributor");
  const engagements = useAdminEngagementsQuery(query, selected);

  if (engagements.isPending && !engagements.data) return <PageSkeleton />;
  const data = engagements.data;
  if (!data) return <ErrorNote error={engagements.error} />;
  const rows = data.rows.filter((row) => classification === "all" || row.classification === classification);
  const current = data.selected;

  const tabs = [
    { key: "engagements" as const, label: "Engagements", count: data.tabCounts.engagements },
    { key: "deliverables" as const, label: "Deliverables", count: data.tabCounts.deliverables },
    { key: "retention-exceptions" as const, label: "Retention exceptions", count: data.tabCounts.retentionExceptions },
    { key: "export-requests" as const, label: "Export requests", count: data.tabCounts.exportRequests },
  ];

  return (
    <PageFrame
      breadcrumb="Admin console / Engagements & deliverables"
      title="Engagement oversight"
      subtitle="Manage ownership, access and lifecycle controls. Content and artifact approvals remain with assigned engagement reviewers."
      actions={<ExportButton report="engagements" label="Export inventory" />}
    >
      <EngagementTabs tabs={tabs} active={tab} onChange={setTab} />

      {tab === "engagements" ? (
        <>
          <div className="flex flex-wrap items-center gap-3">
            <Input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search engagement or ID"
              className="min-w-[260px] flex-1"
            />
            <Select
              aria-label="Classification"
              value={classification}
              onChange={(e) => setClassification(e.target.value)}
              className="w-auto"
            >
              <option value="all">Classification: All</option>
              <option value="Internal">Classification: Internal</option>
              <option value="Restricted">Classification: Restricted</option>
            </Select>
            <span className="ml-auto text-xs text-[var(--text-muted)]">
              {rows.length} of {data.totalCount} engagements
            </span>
          </div>

          <AdminEngagementsTable rows={rows} activeId={current?.id ?? ""} onSelect={setSelected} />

          {current ? (
            <div className="grid gap-4 lg:grid-cols-2">
              <SelectedEngagementPanel
                engagement={current}
                actions={
                  <div className="flex flex-wrap items-start gap-2">
                    <ReasonAction
                      label="Manage access"
                      build={(reason) => ({ path: `/engagements/${current.id}/members`, body: { email, role, reason } })}
                    >
                      <Input
                        type="email"
                        required
                        aria-label="Organization member email"
                        placeholder="name@deloitte.com"
                        value={email}
                        onChange={(e) => setEmail(e.target.value)}
                      />
                      <Select aria-label="Role" value={role} onChange={(e) => setRole(e.target.value)}>
                        {data.roles.map((option) => (
                          <option key={option}>{option}</option>
                        ))}
                      </Select>
                    </ReasonAction>
                    <ReasonAction
                      label="Adjust retention"
                      build={(reason) => ({ path: `/engagements/${current.id}/retention`, body: { days: Number(days), reason } })}
                    >
                      <label className="grid gap-1.5 text-2xs font-semibold uppercase tracking-wide text-[var(--text-muted)]">
                        Days after close (currently {current.retentionDays})
                        <Input type="number" min={30} max={3650} required value={days} onChange={(e) => setDays(e.target.value)} />
                      </label>
                    </ReasonAction>
                    <ReasonAction
                      label={current.status === "archived" ? "Archived" : "Archive"}
                      disabled={current.status === "archived" || !current.archiveReady}
                      hint="Open reviews must be closed before archiving"
                      build={(reason) => ({ path: `/engagements/${current.id}/archive`, body: { reason } })}
                    />
                  </div>
                }
              />
              <DeliverableLifecyclePanel items={data.deliverableLifecycle} />
            </div>
          ) : null}
        </>
      ) : null}

      {tab === "deliverables" ? (
        <RecordsTable
          title="Deliverable oversight"
          columns={[
            ["name", "Artifact"],
            ["engagement", "Engagement"],
            ["version", "Version"],
            ["owner", "Owner"],
            ["state", "State"],
          ]}
          rows={data.deliverables}
          empty="No artifacts have been drafted yet."
          action={(row) => <Link href={`/reviews/${row.id}`}>Open review</Link>}
        />
      ) : null}

      {tab === "retention-exceptions" ? (
        <RecordsTable
          title="Exception requests"
          columns={[
            ["id", "Request"],
            ["engagement", "Engagement"],
            ["requested", "Requested retention"],
            ["owner", "Owner"],
            ["approver", "Approver"],
            ["state", "State"],
            ["justification", "Business justification"],
          ]}
          rows={data.retentionExceptions}
          empty="No retention exceptions have been requested."
        />
      ) : null}

      {tab === "export-requests" ? (
        <RecordsTable
          title="Requested packages"
          columns={[
            ["id", "Request"],
            ["artifact", "Artifact"],
            ["requestedBy", "Requested by"],
            ["engagement", "Engagement"],
            ["gates", "Gates"],
            ["state", "State"],
          ]}
          rows={data.exportRequests}
          empty="No export requests are waiting."
          action={(row) =>
            row.state === "Released" ? (
              "Released"
            ) : (
              <ReasonAction
                label="Approve export"
                build={(reason) => ({ path: `/export-requests/${row.id}/approve`, body: { reason } })}
              />
            )
          }
        />
      ) : null}
    </PageFrame>
  );
}
