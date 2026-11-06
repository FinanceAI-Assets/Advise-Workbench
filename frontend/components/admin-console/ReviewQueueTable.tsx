"use client";

import { DataTable, type DataTableColumn } from "@/components/ui/DataTable";
import { StatusBadge } from "@/components/ui/StatusBadge";
import type { ReviewQueueRow } from "@/types/api";

const COLUMNS: DataTableColumn<ReviewQueueRow>[] = [
  { key: "item", header: "Item / reference", sortValue: (row) => row.itemReference, cell: (row) => <span className="font-semibold text-[var(--text-default)]">{row.itemReference}</span> },
  { key: "reviewer", header: "Reviewer", sortValue: (row) => row.reviewer, cell: (row) => row.reviewer },
  { key: "type", header: "Type", sortValue: (row) => row.type, hideBelow: "md", cell: (row) => <span className="text-[var(--text-muted)]">{row.type}</span> },
  { key: "state", header: "State", sortValue: (row) => row.state, cell: (row) => <StatusBadge>{row.state}</StatusBadge> },
];

/** Open reviews; selecting a row shows it in the panel beside the table. */
export function ReviewQueueTable({ rows, activeId, onSelect }: { rows: ReviewQueueRow[]; activeId: string; onSelect: (id: string) => void }) {
  return (
    <DataTable
      label="Review queue"
      itemName="reviews"
      columns={COLUMNS}
      rows={rows}
      rowKey={(row) => row.id}
      onRowClick={(row) => onSelect(row.id)}
      isRowActive={(row) => row.id === activeId}
      minWidth="min-w-[560px]"
    />
  );
}
