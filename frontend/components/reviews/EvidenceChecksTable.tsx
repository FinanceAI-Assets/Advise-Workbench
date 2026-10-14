import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import type { EvidenceCheckRow } from "@/types/api";

const RESULT_CLASS: Record<EvidenceCheckRow["result"], string> = {
  Passed: "border-[var(--surface-border)] bg-[#EFF6E6] text-[#356B12]",
  Gap: "border-[var(--surface-border)] bg-[#FCF3E2] text-[#8C5B12]",
};

export function EvidenceChecksTable({ checks, runMeta }: { checks: EvidenceCheckRow[]; runMeta: string }) {
  return (
    <Card className="space-y-3 overflow-hidden p-0">
      <div className="flex items-center justify-between p-4 pb-0">
        <h2 className="text-base font-semibold text-[var(--text-default)]">Evidence checks</h2>
        <span className="text-xs text-[var(--text-muted)]">{runMeta}</span>
      </div>
      <table className="w-full text-left text-sm">
        <thead>
          <tr className="border-y border-[var(--surface-border)] bg-[var(--surface-muted)] text-xs text-[var(--text-muted)]">
            <th className="px-4 py-2 font-medium">Check</th>
            <th className="px-4 py-2 font-medium">Result</th>
            <th className="px-4 py-2 font-medium">Action</th>
          </tr>
        </thead>
        <tbody>
          {checks.map((row) => (
            <tr key={row.id} className="border-b border-[var(--surface-border)] last:border-b-0">
              <td className="px-4 py-3 font-medium text-[var(--text-default)]">{row.check}</td>
              <td className="px-4 py-3">
                <Badge className={RESULT_CLASS[row.result]}>{row.resultLabel}</Badge>
              </td>
              <td className="px-4 py-3 text-[var(--text-muted)]">{row.action}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </Card>
  );
}
