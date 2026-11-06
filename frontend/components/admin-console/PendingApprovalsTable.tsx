"use client";

import Link from "next/link";

import { Card } from "@/components/ui/Card";
import { DataTable, type DataTableColumn } from "@/components/ui/DataTable";
import { StatusBadge, type StatusTone } from "@/components/ui/StatusBadge";
import type { PendingApprovalRow } from "@/types/api";

const STATE_TONE: Record<string, StatusTone> = { "Quality review": "neutral" };

const COLUMNS: DataTableColumn<PendingApprovalRow>[] = [
  { key: "item", header: "Item", sortValue: (row) => row.item, cell: (row) => <span className="font-semibold text-[var(--text-default)]">{row.item}</span> },
  { key: "type", header: "Type / version", sortValue: (row) => row.typeVersion, hideBelow: "md", cell: (row) => <span className="text-[var(--text-muted)]">{row.typeVersion}</span> },
  { key: "assigned", header: "Assigned to", sortValue: (row) => row.assignedTo, cell: (row) => row.assignedTo },
  { key: "due", header: "Due", sortValue: (row) => row.due, cell: (row) => <span className="whitespace-nowrap text-[var(--text-muted)]">{row.due}</span> },
  { key: "state", header: "State", sortValue: (row) => row.state, cell: (row) => <StatusBadge tone={STATE_TONE[row.state]}>{row.state}</StatusBadge> },
];

/** The overview's pending approvals: the first few, with a link to the full queue. */
export function PendingApprovalsTable({ rows, total }: { rows: PendingApprovalRow[]; total: number }) {
  return (
    <Card className="overflow-hidden p-0">
      <div className="flex items-center justify-between p-4">
        <h2 className="text-base font-semibold text-[var(--text-default)]">Pending approvals</h2>
        <span className="text-xs text-[var(--text-muted)]">{total} total</span>
      </div>
      <DataTable
        bare
        paginate={false}
        label="Pending approvals"
        columns={COLUMNS}
        rows={rows}
        rowKey={(row) => row.id}
        empty={<p className="text-center text-sm text-[var(--text-muted)]">Nothing is waiting for approval.</p>}
      />
      <div className="border-t border-[var(--surface-border)] px-4 py-3">
        <Link href="/admin/console/reviews" className="text-sm font-medium !text-[var(--accent-green-dark)] !no-underline hover:underline">
          Open full review queue →
        </Link>
      </div>
    </Card>
  );
}
