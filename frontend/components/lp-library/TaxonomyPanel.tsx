import { Card } from "@/components/ui/Card";
import { cn } from "@/lib/utils";
import type { PracticeCategory } from "@/types/api";

export function TaxonomyPanel({
  categories,
  activeId,
  onSelect,
}: {
  categories: PracticeCategory[];
  activeId: string;
  onSelect: (id: string) => void;
}) {
  return (
    <Card className="space-y-1">
      <h2 className="text-base font-semibold text-[var(--text-default)]">Taxonomy</h2>
      <ul className="flex flex-wrap gap-1 lg:block lg:divide-y lg:divide-[var(--surface-border)]">
        {categories.map((category, i) => {
          const active = category.id === activeId;
          return (
            <li key={category.id}>
              <button
                type="button"
                aria-pressed={active}
                disabled={!active && category.count === 0}
                onClick={() => onSelect(category.id)}
                className={cn(
                  "w-full rounded-md px-2 py-2 text-left text-sm transition disabled:cursor-not-allowed disabled:opacity-50 lg:py-3",
                  i === 0 && "font-semibold text-[var(--text-default)]",
                  active
                    ? "bg-[#EFF6E6] font-semibold text-[var(--accent-green-dark)]"
                    : i !== 0 && "text-[var(--text-muted)] enabled:hover:bg-[var(--surface-muted)]"
                )}
              >
                {category.label} · {category.count}
              </button>
            </li>
          );
        })}
      </ul>
      <p className="hidden border-t border-[var(--surface-border)] pt-3 text-xs text-[var(--text-muted)] lg:block">
        Library access follows your role and engagement permissions.
      </p>
    </Card>
  );
}
