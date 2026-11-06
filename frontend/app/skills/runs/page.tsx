"use client";

import Link from "next/link";
import { useState } from "react";

import { DataTable, DataTableToolbar } from "@/components/ui/DataTable";
import { EmptyState } from "@/components/ui/EmptyState";
import { StatusBadge, type StatusTone } from "@/components/ui/StatusBadge";
import { BackButton } from "@/components/workbench/BackButton";
import { ErrorNote, PageFrame, PageSkeleton } from "@/components/workbench/PageFrame";
import { useSkillRunsQuery } from "@/hooks/useWorkbench";

const STATUS_TONE: Record<string, StatusTone> = {
  done: "success",
  review_ready: "success",
  approved: "warning",
  plan_ready: "warning",
  failed: "error",
};

export default function SkillRunHistoryPage() {
  const runs = useSkillRunsQuery();
  const [query, setQuery] = useState("");
  if (runs.isPending) return <PageSkeleton />;
  const items = runs.data?.items ?? [];
  const needle = query.trim().toLowerCase();
  const visible = needle
    ? items.filter((run) => [run.id, run.instruction, run.engagement, run.skill, run.status].some((v) => String(v ?? "").toLowerCase().includes(needle)))
    : items;

  return (
    <PageFrame
      back={<BackButton href="/skills" label="Back to skills" />}
      breadcrumb={
        <>
          User workspace / <Link href="/skills">Skills</Link> / Skill run history
        </>
      }
      title="Skill run history"
      subtitle="Runs across your engagements, with their outputs and status."
    >
      <ErrorNote error={runs.error} />
      {items.length === 0 ? (
        <EmptyState title="No runs yet" description="Run a skill in an engagement to see it here." />
      ) : (
        <>
          <DataTableToolbar search={query} onSearch={setQuery} searchLabel="Search runs" placeholder="Search by run, engagement or skill" />
          <DataTable
            label="Skill runs"
            itemName="runs"
            rows={visible}
            rowKey={(run) => run.id}
            rowHref={(run) => `/engagements/${run.projectId}/deliverables`}
            minWidth="min-w-[820px]"
            empty={<p className="text-center text-sm text-[var(--text-muted)]">No runs match your search.</p>}
            columns={[
              {
                key: "run",
                header: "Run",
                sortValue: (run) => run.id,
                cell: (run) => (
                  <>
                    <span className="block font-semibold text-[var(--text-default)] group-hover:text-[var(--accent-green-dark)]">{run.id}</span>
                    <span className="block max-w-[320px] truncate text-xs text-[var(--text-muted)]" title={run.instruction}>
                      {run.instruction}
                    </span>
                  </>
                ),
              },
              { key: "engagement", header: "Engagement", sortValue: (run) => run.engagement, cell: (run) => run.engagement },
              { key: "skill", header: "Skill", sortValue: (run) => run.skill, cell: (run) => run.skill },
              { key: "outputs", header: "Outputs", hideBelow: "lg", cell: (run) => <span className="text-[var(--text-muted)]">{run.outputs}</span> },
              { key: "when", header: "Date", sortValue: (run) => run.when, cell: (run) => <span className="whitespace-nowrap text-[var(--text-muted)]">{run.when}</span> },
              {
                key: "status",
                header: "Status",
                sortValue: (run) => run.status,
                cell: (run) => <StatusBadge tone={STATUS_TONE[run.status]}>{run.status.replaceAll("_", " ")}</StatusBadge>,
              },
            ]}
          />
        </>
      )}
    </PageFrame>
  );
}
