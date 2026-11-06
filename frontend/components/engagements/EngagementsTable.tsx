"use client";

import { EngagementProgressBar } from "@/components/engagements/EngagementProgressBar";
import { EngagementStageBadge } from "@/components/engagements/EngagementStageBadge";
import { DataTable, type DataTableColumn } from "@/components/ui/DataTable";
import type { EngagementRow } from "@/types/api";

const COLUMNS: DataTableColumn<EngagementRow>[] = [
  {
    key: "engagement",
    header: "Engagement",
    sortValue: (row) => row.name,
    cell: (row) => (
      <>
        <span className="block font-semibold text-[var(--text-default)] group-hover:text-[var(--accent-green-dark)]">{row.name}</span>
        <span className="block text-xs text-[var(--text-muted)]">
          {row.code} · {row.type}
        </span>
      </>
    ),
  },
  { key: "stage", header: "Stage", sortValue: (row) => row.stage, cell: (row) => <EngagementStageBadge stage={row.stage} /> },
  { key: "progress", header: "Progress", sortValue: (row) => row.progress, width: "w-40", cell: (row) => <EngagementProgressBar value={row.progress} /> },
  { key: "owner", header: "Owner", sortValue: (row) => row.owner, hideBelow: "md", cell: (row) => row.owner },
  { key: "next", header: "Next task", hideBelow: "lg", cell: (row) => <span className="text-[var(--text-muted)]">{row.nextTask}</span> },
  { key: "due", header: "Due", sortValue: (row) => row.dueDate, cell: (row) => <span className="whitespace-nowrap text-[var(--text-muted)]">{row.dueDate}</span> },
];

/** One page of engagements (the page pages them on the server); the first, most recent, leads in green. */
export function EngagementsTable({ rows }: { rows: EngagementRow[] }) {
  return (
    <DataTable
      label="Engagements"
      paginate={false}
      columns={COLUMNS}
      rows={rows}
      rowKey={(row) => row.id}
      rowHref={(row) => `/engagements/${row.id}`}
      isRowActive={(row) => row.id === rows[0]?.id}
      minWidth="min-w-[720px]"
    />
  );
}
