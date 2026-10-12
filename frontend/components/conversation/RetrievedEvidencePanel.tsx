import { ListFilter } from "lucide-react";

import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import type { EvidenceMatch } from "@/types/api";

export function RetrievedEvidencePanel({
  evidence,
  shown,
  total,
}: {
  evidence: EvidenceMatch[];
  shown: number;
  total: number;
}) {
  return (
    <Card className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-base font-semibold text-[var(--text-default)]">Retrieved evidence</h2>
        <span className="text-xs text-[var(--text-muted)]">
          {shown} of {total}
        </span>
      </div>
      <div className="flex items-center justify-between text-xs text-[var(--text-muted)]">
        <span>Ranked by relevance</span>
        <ListFilter size={14} aria-hidden />
      </div>
      <ul className="space-y-4">
        {evidence.map((item) => (
          <li key={item.id} className="space-y-1 border-b border-[var(--surface-border)] pb-4 last:border-b-0 last:pb-0">
            <div className="flex items-center justify-between">
              <span className="rounded-md border border-[var(--surface-border)] bg-[#EFF6E6] px-2 py-0.5 text-xs font-semibold text-[#356B12]">
                [{item.index}]
              </span>
              <span className="text-xs font-semibold text-[#356B12]">{item.relevance}% relevant</span>
            </div>
            <p className="text-sm font-semibold text-[var(--text-default)]">{item.title}</p>
            <p className="text-xs text-[var(--text-muted)]">{item.source}</p>
            <p className="text-sm italic text-[var(--text-default)]">&ldquo;{item.quote}&rdquo;</p>
            <p className="text-xs text-[var(--text-muted)]">{item.attribution}</p>
          </li>
        ))}
      </ul>
      <Button variant="secondary" type="button" className="w-full text-sm">
        View all {total} matches
      </Button>
    </Card>
  );
}
