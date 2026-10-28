import { CheckCircle2, MessageSquare, PenLine } from "lucide-react";

import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import type { ApprovalEvent } from "@/types/api";

const ICONS = {
  check: CheckCircle2,
  comment: MessageSquare,
  edit: PenLine,
} as const;

export function ApprovalPanel({
  approverName,
  approverRole,
  status,
  timeline,
}: {
  approverName: string;
  approverRole: string;
  status: string;
  timeline: ApprovalEvent[];
}) {
  return (
    <Card className="space-y-4">
      <h2 className="text-base font-semibold text-[var(--text-default)]">Approval &amp; submission</h2>
      <div className="flex items-start justify-between gap-2">
        <div>
          <p className="text-2xs font-semibold uppercase tracking-wide text-[var(--text-muted)]">Approver</p>
          <p className="text-sm font-semibold text-[var(--text-default)]">
            {approverName} · {approverRole}
          </p>
        </div>
        <Badge className="shrink-0 border-[var(--surface-border)] bg-[#FCF3E2] text-[#8C5B12]">{status}</Badge>
      </div>
      <ul className="space-y-3">
        {timeline.map((event) => {
          const Icon = ICONS[event.icon] ?? ICONS.edit;
          return (
            <li key={event.id} className="flex items-start gap-3">
              <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-[var(--surface-muted)] text-[var(--text-muted)]">
                <Icon size={14} aria-hidden />
              </span>
              <div>
                <p className="text-sm font-semibold text-[var(--text-default)]">{event.title}</p>
                <p className="text-xs text-[var(--text-muted)]">{event.attribution}</p>
              </div>
            </li>
          );
        })}
      </ul>
    </Card>
  );
}
