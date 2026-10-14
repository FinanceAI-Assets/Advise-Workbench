import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import type { Milestone, MilestoneStatus } from "@/types/api";

// Same sampled palette as EngagementStageBadge — Complete/Drafting/Scheduled
// map to the same green/blue/gray treatment used for engagement stages.
const STATUS_CLASS: Record<MilestoneStatus, string> = {
  Complete: "border-[var(--surface-border)] bg-[#EFF6E6] text-[#356B12]",
  Drafting: "border-[var(--surface-border)] bg-[#EDF2F6] text-[#3B596F]",
  Scheduled: "border-[var(--surface-border)] bg-[#F4F5F3] text-[#677067]",
};

export function MilestonesTable({ milestones }: { milestones: Milestone[] }) {
  return (
    <Card className="space-y-3 p-0 overflow-hidden">
      <div className="flex items-center justify-between p-4 pb-0">
        <h2 className="text-base font-semibold text-[var(--text-default)]">Milestones &amp; next steps</h2>
        <span className="text-xs text-[var(--text-muted)]">{milestones.length} milestones</span>
      </div>
      <table className="w-full text-left text-sm">
        <thead>
          <tr className="border-y border-[var(--surface-border)] bg-[var(--surface-muted)] text-xs text-[var(--text-muted)]">
            <th className="px-4 py-2 font-medium">Milestone</th>
            <th className="px-4 py-2 font-medium">Owner</th>
            <th className="px-4 py-2 font-medium">Target</th>
            <th className="px-4 py-2 font-medium">Status</th>
          </tr>
        </thead>
        <tbody>
          {milestones.map((m) => (
            <tr key={m.id} className="border-b border-[var(--surface-border)] last:border-b-0">
              <td className="px-4 py-3 font-medium text-[var(--text-default)]">{m.name}</td>
              <td className="px-4 py-3 text-[var(--text-default)]">{m.owner}</td>
              <td className="px-4 py-3 text-[var(--text-muted)]">{m.target}</td>
              <td className="px-4 py-3">
                <Badge className={STATUS_CLASS[m.status]}>{m.status}</Badge>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </Card>
  );
}
