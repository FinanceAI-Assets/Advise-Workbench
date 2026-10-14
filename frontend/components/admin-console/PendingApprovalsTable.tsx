import Link from "next/link";
import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import { cn } from "@/lib/utils";
import type { PendingApprovalRow } from "@/types/api";

const STATE_CLASS: Record<string, string> = {
  "Quality review": "border-[var(--surface-border)] bg-[var(--surface-muted)] text-[var(--text-muted)]",
  Approval: "border-[var(--surface-border)] bg-[#FCF3E2] text-[#8C5B12]",
  "In review": "border-[var(--surface-border)] bg-[#FCF3E2] text-[#8C5B12]",
  "Changes requested": "border-[var(--surface-border)] bg-[#FCF3E2] text-[#8C5B12]",
};

export function PendingApprovalsTable({ rows, total }: { rows: PendingApprovalRow[]; total: number }) {
  return (
    <Card className="space-y-3 overflow-hidden p-0">
      <div className="flex items-center justify-between p-4 pb-0">
        <h2 className="text-base font-semibold text-[var(--text-default)]">Pending approvals</h2>
        <span className="text-xs text-[var(--text-muted)]">{total} total</span>
      </div>
      <table className="w-full text-left text-sm">
        <thead>
          <tr className="border-y border-[var(--surface-border)] bg-[var(--surface-muted)] text-xs text-[var(--text-muted)]">
            <th className="px-4 py-2 font-medium">Item</th>
            <th className="px-4 py-2 font-medium">Type / version</th>
            <th className="px-4 py-2 font-medium">Assigned to</th>
            <th className="px-4 py-2 font-medium">Due</th>
            <th className="px-4 py-2 font-medium">State</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.id} className="border-b border-[var(--surface-border)] last:border-b-0">
              <td className="px-4 py-3 font-medium text-[var(--text-default)]">{row.item}</td>
              <td className="px-4 py-3 text-[var(--text-muted)]">{row.typeVersion}</td>
              <td className="px-4 py-3 text-[var(--text-default)]">{row.assignedTo}</td>
              <td className="px-4 py-3 text-[var(--text-muted)]">{row.due}</td>
              <td className="px-4 py-3">
                <Badge className={cn("whitespace-nowrap", STATE_CLASS[row.state] ?? "border-[var(--surface-border)] bg-white text-[var(--text-muted)]")}>
                  {row.state}
                </Badge>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="p-4 pt-0">
        <Link href="/admin/console/reviews" className="text-sm font-medium !text-[var(--accent-green-dark)] !no-underline hover:underline">
          Open full review queue →
        </Link>
      </div>
    </Card>
  );
}
