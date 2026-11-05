import { cn } from "@/lib/utils";
import type { SkillRegistryItem } from "@/types/api";

export function SkillRegistryList({
  items,
  activeId,
  onSelect,
}: {
  items: SkillRegistryItem[];
  activeId: string;
  onSelect: (id: string) => void;
}) {
  return (
    <div className="space-y-2">
      <h2 className="px-1 text-base font-semibold text-[var(--text-default)]">Skill registry</h2>
      <ul className="space-y-1">
        {items.map((item) => {
          const active = item.id === activeId;
          return (
            <li key={item.id}>
              <button
                type="button"
                onClick={() => onSelect(item.id)}
                className={cn(
                  "w-full rounded-md border-l-2 p-3 text-left transition",
                  active ? "border-l-[var(--accent-green)] bg-[#EFF6E6]" : "border-l-transparent hover:bg-[var(--surface-muted)]"
                )}
              >
                <p className={cn("text-sm font-semibold", active ? "text-[var(--accent-green-dark)]" : "text-[var(--text-default)]")}>
                  {item.name}
                </p>
                <p className="text-xs text-[var(--text-muted)]">{item.candidateMeta}</p>
                <p className="text-xs text-[var(--text-muted)]">{item.publishedMeta}</p>
              </button>
            </li>
          );
        })}
      </ul>
      <p className="px-1 text-xs text-[var(--text-muted)]">
        Published definitions are immutable. Changes create a new candidate version.
      </p>
    </div>
  );
}
