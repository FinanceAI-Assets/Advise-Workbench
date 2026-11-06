"use client";

import { Card } from "@/components/ui/Card";
import { DataTable, type DataTableColumn } from "@/components/ui/DataTable";
import { StatusBadge, type StatusTone } from "@/components/ui/StatusBadge";
import type { RiskQueueRow } from "@/types/api";

const SEVERITY_TONE: Record<RiskQueueRow["severity"], StatusTone> = { High: "error", Medium: "warning", Low: "neutral" };
const SEVERITY_ORDER: Record<RiskQueueRow["severity"], number> = { High: 0, Medium: 1, Low: 2 };

const COLUMNS: DataTableColumn<RiskQueueRow>[] = [
  { key: "risk", header: "Risk / scope", sortValue: (row) => row.riskScope, cell: (row) => <span className="font-semibold text-[var(--text-default)]">{row.riskScope}</span> },
  {
    key: "severity",
    header: "Severity",
    sortValue: (row) => SEVERITY_ORDER[row.severity],
    cell: (row) => <StatusBadge tone={SEVERITY_TONE[row.severity]}>{row.severity}</StatusBadge>,
  },
  { key: "owner", header: "Owner", sortValue: (row) => row.owner, cell: (row) => row.owner },
  { key: "control", header: "Control", sortValue: (row) => row.control, hideBelow: "md", cell: (row) => <span className="text-[var(--text-muted)]">{row.control}</span> },
];

export function RiskQueueTable({ rows, openCount, footnote }: { rows: RiskQueueRow[]; openCount: number; footnote: string }) {
  return (
    <Card className="overflow-hidden p-0">
      <div className="flex items-center justify-between p-4">
        <h2 className="text-base font-semibold text-[var(--text-default)]">Risk queue</h2>
        <span className="text-xs text-[var(--text-muted)]">{openCount} open</span>
      </div>
      <DataTable
        bare
        paginate={false}
        label="Risk queue"
        columns={COLUMNS}
        rows={rows}
        rowKey={(row) => row.id}
        empty={<p className="text-center text-sm text-[var(--text-muted)]">No open risks.</p>}
      />
      <p className="border-t border-[var(--surface-border)] px-4 py-3 text-xs text-[var(--text-muted)]">{footnote}</p>
    </Card>
  );
}
