import { Button } from "@/components/ui/Button";
import { cn } from "@/lib/utils";
import type { RecentConversationItem } from "@/types/api";

export function RecentConversationsList({
  items,
  onSelect,
}: {
  items: RecentConversationItem[];
  onSelect?: (id: string) => void;
}) {
  return (
    <div className="space-y-2 px-1">
      <p className="text-2xs font-semibold uppercase tracking-wide text-[var(--text-muted)]">Recent conversations</p>
      <ul className="space-y-1">
        {items.map((item) => (
          <li key={item.id}>
            <Button
              type="button"
              variant="ghost"
              disabled={item.active || !onSelect}
              onClick={() => onSelect?.(item.id)}
              className={cn(
                "w-full truncate px-0 py-1 text-left text-sm disabled:opacity-100",
                item.active
                  ? "font-semibold text-[var(--text-default)]"
                  : "text-[var(--text-muted)] hover:text-[var(--text-default)]"
              )}
            >
              {item.label}
            </Button>
          </li>
        ))}
      </ul>
    </div>
  );
}
