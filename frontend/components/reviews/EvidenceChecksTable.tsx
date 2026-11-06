"use client";

import { Card } from "@/components/ui/Card";
import { DataTable, type DataTableColumn } from "@/components/ui/DataTable";
import { StatusBadge } from "@/components/ui/StatusBadge";
import type { EvidenceCheckRow } from "@/types/api";

const COLUMNS: DataTableColumn<EvidenceCheckRow>[] = [
  { key: "check", header: "Check", sortValue: (row) => row.check, cell: (row) => <span className="font-semibold text-[var(--text-default)]">{row.check}</span> },
  {
    key: "result",
    header: "Result",
    // Gaps first.
    sortValue: (row) => (row.result === "Gap" ? 0 : 1),
    cell: (row) => <StatusBadge tone={row.result === "Passed" ? "success" : "warning"}>{row.resultLabel}</StatusBadge>,
  },
  { key: "action", header: "Action", cell: (row) => <span className="text-[var(--text-muted)]">{row.action}</span> },
];

export function EvidenceChecksTable({ checks, runMeta }: { checks: EvidenceCheckRow[]; runMeta: string }) {
  return (
    <Card className="overflow-hidden p-0">
      <div className="flex items-center justify-between gap-3 p-4">
        <h2 className="text-base font-semibold text-[var(--text-default)]">Evidence checks</h2>
        <span className="text-xs text-[var(--text-muted)]">{runMeta}</span>
      </div>
      <DataTable
        bare
        paginate={false}
        label="Evidence checks"
        columns={COLUMNS}
        rows={checks}
        rowKey={(row) => row.id}
        empty={<p className="text-center text-sm text-[var(--text-muted)]">No evidence checks have run.</p>}
      />
    </Card>
  );
}
