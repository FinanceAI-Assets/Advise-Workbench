import type { ReactNode } from "react";
import { Card } from "@/components/ui/Card";
import type { ReleaseApprovalDetail } from "@/types/api";

const STATE_CLASS: Record<string, string> = {
  Pending: "text-[#8C5B12]",
  Blocked: "text-[#A53E37]",
  Passed: "text-[#356B12]",
};

export function ReleaseApprovalPanel({ approval, actions }: { approval: ReleaseApprovalDetail; actions?: ReactNode }) {
  return (
    <Card className="space-y-4">
      <h2 className="text-base font-semibold text-[var(--text-default)]">Release approval</h2>
      <div>
        <p className="text-2xs font-semibold uppercase tracking-wide text-[var(--text-muted)]">Reviewer</p>
        <p className="text-sm font-semibold text-[var(--text-default)]">
          {approval.reviewerName} · {approval.reviewerRole}
        </p>
      </div>
      <ul className="space-y-2">
        {approval.checks.map((check) => (
          <li key={check.id} className="flex items-center justify-between text-sm">
            <span className="text-[var(--text-default)]">{check.label}</span>
            <span className={STATE_CLASS[check.state] ?? "text-[var(--text-muted)]"}>{check.state}</span>
          </li>
        ))}
      </ul>
      <p className="text-xs text-[var(--text-muted)]">{approval.footnote}</p>
      {actions}
    </Card>
  );
}
