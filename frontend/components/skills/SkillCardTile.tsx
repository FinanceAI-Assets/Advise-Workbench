import { Check, Workflow } from "lucide-react";

import { cn } from "@/lib/utils";
import type { SkillCardSummary } from "@/types/api";

export function SkillCardTile({
  skill,
  active,
  onSelect,
}: {
  skill: SkillCardSummary;
  active: boolean;
  onSelect: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onSelect}
      className={cn(
        "w-full space-y-3 rounded-lg border bg-white p-4 text-left transition",
        active ? "border-[var(--accent-green)] shadow-sm" : "border-[var(--surface-border)] hover:border-[var(--accent-green)]"
      )}
    >
      <div className="flex items-center justify-between">
        <span className="flex h-9 w-9 items-center justify-center rounded-md bg-[#EFF6E6] text-[var(--accent-green-dark)]">
          <Workflow size={16} aria-hidden />
        </span>
        <span className="rounded-md bg-[var(--surface-muted)] px-2 py-0.5 text-xs text-[var(--text-muted)]">
          {skill.versionLabel}
        </span>
      </div>
      <div>
        <p className="font-semibold text-[var(--text-default)]">{skill.name}</p>
        <p className="text-sm text-[var(--text-muted)]">{skill.description}</p>
      </div>
      <div className="flex items-center justify-between">
        <span className="rounded-md bg-[var(--surface-muted)] px-2 py-0.5 text-xs text-[var(--text-muted)]">
          {skill.formats}
        </span>
        {skill.published ? (
          <span className="flex items-center gap-1 text-xs font-medium text-[var(--accent-green-dark)]">
            Published
            <Check size={12} aria-hidden />
          </span>
        ) : null}
      </div>
    </button>
  );
}
