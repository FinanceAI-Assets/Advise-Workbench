import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import type { RiskQueueRow } from "@/types/api";

const SEVERITY_CLASS: Record<RiskQueueRow["severity"], string> = {
  High: "border-[var(--surface-border)] bg-[#FBEFEB] text-[#A53E37]",
  Medium: "border-[var(--surface-border)] bg-[#FCF3E2] text-[#8C5B12]",
  Low: "border-[var(--surface-border)] bg-[var(--surface-muted)] text-[var(--text-muted)]",
};

export function RiskQueueTable({
  rows,
  openCount,
  footnote,
}: {
  rows: RiskQueueRow[];
  openCount: number;
  footnote: string;
}) {
  return (
    <Card className="space-y-3 overflow-hidden p-0">
      <div className="flex items-center justify-between p-4 pb-0">
        <h2 className="text-base font-semibold text-[var(--text-default)]">Risk queue</h2>
        <span className="text-xs text-[var(--text-muted)]">{openCount} open</span>
      </div>
      <table className="w-full text-left text-sm">
        <thead>
          <tr className="border-y border-[var(--surface-border)] bg-[var(--surface-muted)] text-xs text-[var(--text-muted)]">
            <th className="px-4 py-2 font-medium">Risk / scope</th>
            <th className="px-4 py-2 font-medium">Severity</th>
            <th className="px-4 py-2 font-medium">Owner</th>
            <th className="px-4 py-2 font-medium">Control</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.id} className="border-b border-[var(--surface-border)] last:border-b-0">
              <td className="px-4 py-3 font-medium text-[var(--text-default)]">{row.riskScope}</td>
              <td className="px-4 py-3">
                <Badge className={SEVERITY_CLASS[row.severity]}>{row.severity}</Badge>
              </td>
              <td className="px-4 py-3 text-[var(--text-default)]">{row.owner}</td>
              <td className="px-4 py-3 text-[var(--text-muted)]">{row.control}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="p-4 pt-0 text-xs text-[var(--text-muted)]">{footnote}</p>
    </Card>
  );
}
