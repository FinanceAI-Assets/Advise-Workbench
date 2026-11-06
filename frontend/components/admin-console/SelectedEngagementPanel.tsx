"use client";

import type { ReactNode } from "react";

import { Card } from "@/components/ui/Card";
import { DataTable, type DataTableColumn } from "@/components/ui/DataTable";
import type { SelectedEngagementDetail } from "@/types/api";

type Member = SelectedEngagementDetail["members"][number];

const MEMBER_COLUMNS: DataTableColumn<Member>[] = [
  { key: "name", header: "Member", sortValue: (m) => m.name, cell: (m) => <span className="font-semibold text-[var(--text-default)]">{m.name}</span> },
  { key: "role", header: "Role", sortValue: (m) => m.role, cell: (m) => <span className="text-[var(--text-muted)]">{m.role}</span> },
  { key: "permission", header: "Permission", sortValue: (m) => m.permission, cell: (m) => <span className="text-[var(--text-muted)]">{m.permission}</span> },
];

function MetaField({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-2xs font-semibold uppercase tracking-wide text-[var(--text-muted)]">{label}</p>
      <p className="text-sm font-medium text-[var(--text-default)]">{value}</p>
    </div>
  );
}

export function SelectedEngagementPanel({ engagement, actions }: { engagement: SelectedEngagementDetail; actions?: ReactNode }) {
  return (
    <Card className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-base font-semibold text-[var(--text-default)]">Selected: {engagement.name}</h2>
        <span className="text-xs text-[var(--text-muted)]">{engagement.code}</span>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <MetaField label="Access group" value={engagement.accessGroup} />
        <MetaField label="Content access" value={engagement.contentAccess} />
        <MetaField label="Retention policy" value={engagement.retentionPolicy} />
        <MetaField label="Scheduled disposition" value={engagement.scheduledDisposition} />
      </div>

      <div className="overflow-hidden rounded-md border border-[var(--surface-border)]">
        <DataTable
          bare
          paginate={false}
          label="Engagement members"
          columns={MEMBER_COLUMNS}
          rows={engagement.members}
          rowKey={(member) => member.id}
          empty={<p className="text-center text-sm text-[var(--text-muted)]">No members yet.</p>}
        />
      </div>

      {actions}
    </Card>
  );
}
