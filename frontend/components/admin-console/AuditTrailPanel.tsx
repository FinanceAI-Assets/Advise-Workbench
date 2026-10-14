import Link from "next/link";
import { CheckCircle2, History, MessageSquare, Send } from "lucide-react";

import { Card } from "@/components/ui/Card";
import type { AuditTrailEvent } from "@/types/api";

const ICONS = {
  check: CheckCircle2,
  history: History,
  send: Send,
  comment: MessageSquare,
} as const;

export function AuditTrailPanel({ events }: { events: AuditTrailEvent[] }) {
  return (
    <Card className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-base font-semibold text-[var(--text-default)]">Audit trail</h2>
        <span className="text-xs text-[var(--text-muted)]">Append-only</span>
      </div>
      <ul className="space-y-3">
        {events.map((event) => {
          const Icon = ICONS[event.icon];
          return (
            <li key={event.id} className="flex items-start gap-3">
              <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-[var(--surface-muted)] text-[var(--text-muted)]">
                <Icon size={14} aria-hidden />
              </span>
              <div>
                <p className="text-sm font-semibold text-[var(--text-default)]">{event.title}</p>
                <p className="text-xs text-[var(--text-muted)]">{event.attribution}</p>
              </div>
            </li>
          );
        })}
      </ul>
      <Link href="/admin/console/reviews?tab=audit" className="text-sm font-medium !text-[var(--accent-green-dark)] !no-underline hover:underline">
        View full audit trail →
      </Link>
    </Card>
  );
}
