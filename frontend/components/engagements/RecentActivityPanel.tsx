import { Library, Presentation } from "lucide-react";

import { Card } from "@/components/ui/Card";
import type { ActivityItem } from "@/types/api";

const ICONS = {
  deck: Presentation,
  library: Library,
} as const;

export function RecentActivityPanel({ items }: { items: ActivityItem[] }) {
  return (
    <Card className="space-y-4">
      <h2 className="text-base font-semibold text-[var(--text-default)]">Recent activity</h2>
      <ul className="space-y-4">
        {items.map((item) => {
          const Icon = ICONS[item.icon];
          return (
            <li key={item.id} className="flex items-start gap-3 border-b border-[var(--surface-border)] pb-4 last:border-b-0 last:pb-0">
              <Icon className="mt-0.5 h-4 w-4 shrink-0 text-[var(--text-muted)]" aria-hidden />
              <div>
                <p className="text-sm font-medium text-[var(--text-default)]">{item.title}</p>
                <p className="text-xs text-[var(--text-muted)]">{item.meta}</p>
              </div>
            </li>
          );
        })}
      </ul>
    </Card>
  );
}
