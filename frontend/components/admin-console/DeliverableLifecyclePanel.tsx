import { CheckCircle2, ClipboardList, FileText, Presentation } from "lucide-react";

import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import { NoticeCard } from "@/components/ui/NoticeCard";
import type { DeliverableLifecycleItem } from "@/types/api";

const ICONS = {
  deck: Presentation,
  doc: FileText,
  evidence: ClipboardList,
} as const;

const STATE_CLASS: Record<string, string> = {
  Locked: "border-[var(--surface-border)] bg-[#FCF3E2] text-[#8C5B12]",
  Current: "border-[var(--surface-border)] bg-[#EFF6E6] text-[#356B12]",
};

export function DeliverableLifecyclePanel({ items }: { items: DeliverableLifecycleItem[] }) {
  return (
    <Card className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-base font-semibold text-[var(--text-default)]">Deliverable lifecycle &amp; export gates</h2>
        <span className="text-xs text-[var(--text-muted)]">{items.length} items</span>
      </div>
      <ul className="space-y-3">
        {items.map((item) => {
          const Icon = ICONS[item.icon];
          return (
            <li key={item.id} className="flex items-start justify-between gap-3">
              <div className="flex items-start gap-3">
                <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-[var(--surface-muted)] text-[var(--text-muted)]">
                  <Icon size={16} aria-hidden />
                </span>
                <div>
                  <p className="text-sm font-medium text-[var(--text-default)]">{item.name}</p>
                  <p className="text-xs text-[var(--text-muted)]">{item.meta}</p>
                </div>
              </div>
              <Badge className={STATE_CLASS[item.state] ?? "border-[var(--surface-border)] bg-white text-[var(--text-muted)]"}>
                {item.state}
              </Badge>
            </li>
          );
        })}
      </ul>
      <NoticeCard
        icon={<CheckCircle2 size={18} aria-hidden />}
        title="Scoped administrative controls"
        description="You can manage metadata, retention and membership. You cannot approve your own artifacts or bypass evidence checks."
      />
    </Card>
  );
}
