import { ClipboardList, FileText, Presentation } from "lucide-react";

import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import type { Deliverable } from "@/types/api";

const ICONS = {
  deck: Presentation,
  doc: FileText,
  evidence: ClipboardList,
} as const;

const STATUS_CLASS: Record<string, string> = {
  "Changes requested": "border-[var(--surface-border)] bg-[#FCF3E2] text-[#8C5B12]",
  Draft: "border-[var(--surface-border)] bg-[#F4F5F3] text-[#677067]",
};

export function DeliverablesStrip({ deliverables }: { deliverables: Deliverable[] }) {
  return (
    <Card className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-base font-semibold text-[var(--text-default)]">Engagement deliverables</h2>
        <span className="text-xs text-[var(--text-muted)]">Latest versions</span>
      </div>
      <div className="flex flex-wrap gap-6">
        {deliverables.map((d) => {
          const Icon = ICONS[d.icon];
          return (
            <div key={d.id} className="flex items-start gap-3">
              <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-[var(--surface-muted)] text-[var(--text-muted)]">
                <Icon size={16} aria-hidden />
              </span>
              <div>
                <div className="flex items-center gap-2">
                  <p className="text-sm font-medium text-[var(--text-default)]">{d.name}</p>
                  {d.status ? (
                    <Badge className={STATUS_CLASS[d.status] ?? "border-[var(--surface-border)] bg-white text-[var(--text-muted)]"}>
                      {d.status}
                    </Badge>
                  ) : null}
                </div>
                <p className="text-xs text-[var(--text-muted)]">{d.meta}</p>
              </div>
            </div>
          );
        })}
      </div>
    </Card>
  );
}
