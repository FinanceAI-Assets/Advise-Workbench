"use client";

import { Card } from "@/components/ui/Card";
import { DataTable, type DataTableColumn } from "@/components/ui/DataTable";
import { StatusBadge, type StatusTone } from "@/components/ui/StatusBadge";
import type { Milestone, MilestoneStatus } from "@/types/api";

// Complete / Drafting / Scheduled use the same green / blue / grey as the engagement stages.
const STATUS_TONE: Record<MilestoneStatus, StatusTone> = { Complete: "success", Drafting: "info", Scheduled: "neutral" };
const STATUS_ORDER: Record<MilestoneStatus, number> = { Complete: 0, Drafting: 1, Scheduled: 2 };

const COLUMNS: DataTableColumn<Milestone>[] = [
  { key: "name", header: "Milestone", sortValue: (m) => m.name, cell: (m) => <span className="font-semibold text-[var(--text-default)]">{m.name}</span> },
  { key: "owner", header: "Owner", sortValue: (m) => m.owner, cell: (m) => m.owner },
  { key: "target", header: "Target", sortValue: (m) => m.target, cell: (m) => <span className="whitespace-nowrap text-[var(--text-muted)]">{m.target}</span> },
  { key: "status", header: "Status", sortValue: (m) => STATUS_ORDER[m.status], cell: (m) => <StatusBadge tone={STATUS_TONE[m.status]}>{m.status}</StatusBadge> },
];

export function MilestonesTable({ milestones }: { milestones: Milestone[] }) {
  return (
    <Card className="overflow-hidden p-0">
      <div className="flex items-center justify-between p-4">
        <h2 className="text-base font-semibold text-[var(--text-default)]">Milestones &amp; next steps</h2>
        <span className="text-xs text-[var(--text-muted)]">{milestones.length} milestones</span>
      </div>
      <DataTable
        bare
        paginate={false}
        label="Milestones"
        columns={COLUMNS}
        rows={milestones}
        rowKey={(m) => m.id}
        empty={<p className="text-center text-sm text-[var(--text-muted)]">No milestones yet.</p>}
      />
    </Card>
  );
}
