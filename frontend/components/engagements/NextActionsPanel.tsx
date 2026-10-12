import { ClipboardCheck, MessagesSquare } from "lucide-react";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import type { NextAction } from "@/types/api";

const ICONS = {
  comment: MessagesSquare,
  review: ClipboardCheck,
} as const;

export function NextActionsPanel({ items }: { items: NextAction[] }) {
  return (
    <Card className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-base font-semibold text-[var(--text-default)]">Your next actions</h2>
        <span className="text-xs text-[var(--text-muted)]">{items.length} priorities</span>
      </div>
      <ul className="space-y-4">
        {items.map((item) => {
          const Icon = ICONS[item.icon];
          return (
            <li key={item.id} className="flex items-start justify-between gap-3 border-b border-[var(--surface-border)] pb-4 last:border-b-0 last:pb-0">
              <div className="flex items-start gap-3">
                <Icon className="mt-0.5 h-4 w-4 shrink-0 text-[var(--text-muted)]" aria-hidden />
                <div>
                  <p className="text-sm font-medium text-[var(--text-default)]">{item.title}</p>
                  <p className="text-xs text-[var(--text-muted)]">{item.description}</p>
                </div>
              </div>
              {item.actionLabel ? (
                <Button variant="secondary" className="shrink-0 px-3 py-1.5 text-xs">
                  {item.actionLabel}
                </Button>
              ) : item.due ? (
                <Badge variant="warning" className="shrink-0 border-[var(--surface-border)] bg-[#FCF3E2] text-[#8C5B12]">
                  {item.due}
                </Badge>
              ) : null}
            </li>
          );
        })}
      </ul>
    </Card>
  );
}
