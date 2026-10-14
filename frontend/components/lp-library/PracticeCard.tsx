import { ArrowUpRight } from "lucide-react";

import { Badge } from "@/components/ui/Badge";
import { cn } from "@/lib/utils";
import type { PracticeCardSummary } from "@/types/api";

export function PracticeCard({
  practice,
  active,
  onSelect,
}: {
  practice: PracticeCardSummary;
  active: boolean;
  onSelect: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onSelect}
      className={cn(
        "w-full space-y-2 rounded-lg border bg-white p-4 text-left transition",
        active ? "border-[var(--accent-green)] shadow-sm" : "border-[var(--surface-border)] hover:border-[var(--accent-green)]"
      )}
    >
      <div className="flex items-start justify-between gap-2">
        <p className="font-semibold text-[var(--text-default)]">{practice.title}</p>
        <ArrowUpRight size={16} className="shrink-0 text-[var(--text-muted)]" aria-hidden />
      </div>
      <p className="text-sm text-[var(--text-muted)]">{practice.description}</p>
      <div className="flex flex-wrap items-center gap-2">
        <Badge className="border-[var(--surface-border)] bg-[#EFF6E6] text-[#356B12]">{practice.status}</Badge>
        <Badge className="border-[var(--surface-border)] bg-[var(--surface-muted)] text-[var(--text-muted)]">
          {practice.maturity}
        </Badge>
        <span className="text-xs text-[var(--text-muted)]">{practice.category}</span>
      </div>
      <p className="text-xs text-[var(--text-muted)]">{practice.versionLabel}</p>
    </button>
  );
}
