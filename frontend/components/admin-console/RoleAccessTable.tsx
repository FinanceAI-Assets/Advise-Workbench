"use client";

import { Card } from "@/components/ui/Card";
import { DataTable, type DataTableColumn } from "@/components/ui/DataTable";
import type { RoleAccessRow } from "@/types/api";

const COLUMNS: DataTableColumn<RoleAccessRow>[] = [
  { key: "role", header: "Role", sortValue: (row) => row.role, cell: (row) => <span className="font-semibold text-[var(--text-default)]">{row.role}</span> },
  { key: "allowed", header: "Allowed", cell: (row) => <span className="text-[var(--text-muted)]">{row.allowed}</span> },
  { key: "restricted", header: "Restricted", cell: (row) => <span className="text-[var(--text-muted)]">{row.restricted}</span> },
];

export function RoleAccessTable({ rows }: { rows: RoleAccessRow[] }) {
  return (
    <Card className="overflow-hidden p-0">
      <div className="flex items-center justify-between p-4">
        <h2 className="text-base font-semibold text-[var(--text-default)]">Role-based access</h2>
        <span className="text-xs text-[var(--text-muted)]">Least privilege</span>
      </div>
      <DataTable bare paginate={false} label="Role-based access" columns={COLUMNS} rows={rows} rowKey={(row) => row.id} />
    </Card>
  );
}
