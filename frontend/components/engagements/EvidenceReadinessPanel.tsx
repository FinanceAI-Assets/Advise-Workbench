import { AlertTriangle } from "lucide-react";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import type { EvidenceSource } from "@/types/api";

export function EvidenceReadinessPanel({
  sourceCount,
  sources,
  warning,
  onViewAll,
}: {
  sourceCount: number;
  sources: EvidenceSource[];
  warning: { title: string; description: string } | null;
  onViewAll?: () => void;
}) {
  return (
    <Card className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-base font-semibold text-[var(--text-default)]">Evidence readiness</h2>
        <span className="text-xs text-[var(--text-muted)]">{sourceCount} sources</span>
      </div>
      <ul className="space-y-3">
        {sources.map((s) => (
          <li key={s.id} className="flex items-center justify-between gap-3 text-sm">
            <span className="text-[var(--text-default)]">{s.label}</span>
            <Badge className="border-[var(--surface-border)] bg-[#EFF6E6] text-[#356B12]">{s.value}</Badge>
          </li>
        ))}
      </ul>
      {warning ? (
        <div className="flex items-start gap-2 rounded-md border border-[#F3E2C0] bg-[#FCF3E2] p-3">
          <AlertTriangle size={16} className="mt-0.5 shrink-0 text-[#8C5B12]" aria-hidden />
          <div>
            <p className="text-sm font-semibold text-[#8C5B12]">{warning.title}</p>
            <p className="text-xs text-[#8C5B12]">{warning.description}</p>
          </div>
        </div>
      ) : null}
      <Button variant="secondary" type="button" className="w-full text-sm" onClick={onViewAll}>
        View all sources
      </Button>
    </Card>
  );
}
