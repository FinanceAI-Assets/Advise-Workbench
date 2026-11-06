"use client";

import { DataTable, type DataTableColumn } from "@/components/ui/DataTable";
import { StatusBadge, type StatusTone } from "@/components/ui/StatusBadge";
import type { AdminEngagementRow } from "@/types/api";

const CONTROL_STATE_TONE: Record<string, StatusTone> = {
  "Export locked": "warning",
  "Review pending": "warning",
  "Access risk": "error",
  "Export permitted": "success",
  "Brief stage": "neutral",
};

const COLUMNS: DataTableColumn<AdminEngagementRow>[] = [
  {
    key: "engagement",
    header: "Engagement / ID",
    sortValue: (row) => row.name,
    cell: (row) => (
      <>
        <span className="block font-semibold text-[var(--text-default)]">{row.name}</span>
        <span className="block text-xs text-[var(--text-muted)]">{row.code}</span>
      </>
    ),
  },
  { key: "owner", header: "Owner / access", sortValue: (row) => row.ownerAccess, cell: (row) => row.ownerAccess },
  { key: "classification", header: "Classification", sortValue: (row) => row.classification, cell: (row) => <span className="text-[var(--text-muted)]">{row.classification}</span> },
  { key: "retention", header: "Retention", sortValue: (row) => row.retention, hideBelow: "lg", cell: (row) => <span className="text-[var(--text-muted)]">{row.retention}</span> },
  { key: "deliverables", header: "Deliverables", sortValue: (row) => row.deliverables, hideBelow: "lg", cell: (row) => <span className="text-[var(--text-muted)]">{row.deliverables}</span> },
  {
    key: "control",
    header: "Control state",
    sortValue: (row) => row.controlState,
    cell: (row) => <StatusBadge tone={CONTROL_STATE_TONE[row.controlState]}>{row.controlState}</StatusBadge>,
  },
];

/** Engagements under oversight; selecting a row opens its controls below the table. */
export function AdminEngagementsTable({ rows, activeId, onSelect }: { rows: AdminEngagementRow[]; activeId: string; onSelect: (id: string) => void }) {
  return (
    <DataTable
      label="Engagements"
      itemName="engagements"
      columns={COLUMNS}
      rows={rows}
      rowKey={(row) => row.id}
      onRowClick={(row) => onSelect(row.id)}
      isRowActive={(row) => row.id === activeId}
      minWidth="min-w-[760px]"
    />
  );
}
