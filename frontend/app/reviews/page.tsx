"use client";

import { useState } from "react";

import { EngagementTabs } from "@/components/engagements";
import { DataTable, DataTableToolbar } from "@/components/ui/DataTable";
import { EmptyState } from "@/components/ui/EmptyState";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { ErrorNote, PageFrame, PageSkeleton } from "@/components/workbench/PageFrame";
import { useReviewsQuery } from "@/hooks/useWorkbench";

type Scope = "mine" | "all";

// Review queue: what is waiting on the signed-in user, and every review they can see.
export default function ReviewsPage() {
  const reviews = useReviewsQuery();
  const [scope, setScope] = useState<Scope>("mine");
  const [query, setQuery] = useState("");

  if (reviews.isPending) return <PageSkeleton />;
  const all = reviews.data?.items ?? [];
  const mine = new Set(reviews.data?.mine ?? []);
  const rows = scope === "mine" ? all.filter((r) => mine.has(r.id)) : all;
  const needle = query.trim().toLowerCase();
  const visible = needle
    ? rows.filter((r) => [r.title, r.id, r.engagement, r.owner, r.reviewer, r.state].some((v) => String(v ?? "").toLowerCase().includes(needle)))
    : rows;

  return (
    <PageFrame
      breadcrumb="User workspace / Reviews"
      title="Reviews"
      subtitle="Independent review of artifact versions. Approval is version-specific and cannot be given by the author."
    >
      <EngagementTabs
        tabs={[
          { key: "mine" as const, label: "Waiting on me", count: mine.size },
          { key: "all" as const, label: "All reviews", count: all.length },
        ]}
        active={scope}
        onChange={setScope}
      />
      <ErrorNote error={reviews.error} />
      {rows.length === 0 ? (
        <EmptyState
          title={scope === "mine" ? "Nothing is waiting on you" : "No reviews yet"}
          description="Submit a draft for review from an engagement's deliverables."
        />
      ) : (
        <>
          <DataTableToolbar search={query} onSearch={setQuery} searchLabel="Search reviews" placeholder="Search by item, engagement, owner or reviewer" />
          <DataTable
            label="Reviews"
            itemName="reviews"
            rows={visible}
            rowKey={(row) => row.id}
            rowHref={(row) => `/reviews/${encodeURIComponent(row.id)}`}
            minWidth="min-w-[860px]"
            empty={<p className="text-center text-sm text-[var(--text-muted)]">No reviews match your search.</p>}
            columns={[
              {
                key: "item",
                header: "Item / reference",
                sortValue: (row) => row.title,
                cell: (row) => (
                  <>
                    <span className="block font-semibold text-[var(--text-default)] group-hover:text-[var(--accent-green-dark)]">{row.title}</span>
                    <span className="block text-xs text-[var(--text-muted)]">{row.id}</span>
                  </>
                ),
              },
              { key: "engagement", header: "Engagement", sortValue: (row) => row.engagement, cell: (row) => <span className="text-[var(--text-muted)]">{row.engagement}</span> },
              { key: "type", header: "Type", sortValue: (row) => row.type, hideBelow: "lg", cell: (row) => row.type },
              { key: "owner", header: "Owner", sortValue: (row) => row.owner, hideBelow: "md", cell: (row) => row.owner },
              { key: "reviewer", header: "Reviewer", sortValue: (row) => row.reviewer, cell: (row) => row.reviewer },
              { key: "due", header: "Due", sortValue: (row) => row.dueDate, cell: (row) => <span className="whitespace-nowrap text-[var(--text-muted)]">{row.dueDate}</span> },
              { key: "state", header: "State", sortValue: (row) => row.state, cell: (row) => <StatusBadge>{row.state}</StatusBadge> },
            ]}
          />
        </>
      )}
    </PageFrame>
  );
}
