import { cn } from "@/lib/utils";
import type { RecentConversationItem } from "@/types/api";

export function RecentConversationsList({ items }: { items: RecentConversationItem[] }) {
  return (
    <div className="space-y-2 px-1">
      <p className="text-2xs font-semibold uppercase tracking-wide text-[var(--text-muted)]">Recent conversations</p>
      <ul className="space-y-2">
        {items.map((item) => (
          <li
            key={item.id}
            className={cn(
              "text-sm",
              item.active ? "font-semibold text-[var(--text-default)]" : "text-[var(--text-muted)]"
            )}
          >
            {item.label}
          </li>
        ))}
      </ul>
    </div>
  );
}
