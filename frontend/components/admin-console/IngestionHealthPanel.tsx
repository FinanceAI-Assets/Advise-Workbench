import type { ReactNode } from "react";
import { AlertCircle, Library, Plug, Upload } from "lucide-react";

import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import { NoticeCard } from "@/components/ui/NoticeCard";
import type { IngestionHealthItem } from "@/types/api";

const ICONS = {
  library: Library,
  upload: Upload,
  plug: Plug,
} as const;

const STATUS_CLASS: Record<IngestionHealthItem["status"], string> = {
  Healthy: "border-[var(--surface-border)] bg-[#EFF6E6] text-[#356B12]",
  Attention: "border-[var(--surface-border)] bg-[#FBEFEB] text-[#A53E37]",
};

export function IngestionHealthPanel({
  items,
  updatedMeta,
  warning,
  actions,
}: {
  items: IngestionHealthItem[];
  updatedMeta: string;
  warning: { title: string; description: string } | null;
  actions?: ReactNode;
}) {
  return (
    <Card className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-base font-semibold text-[var(--text-default)]">Ingestion health</h2>
        <span className="text-xs text-[var(--text-muted)]">{updatedMeta}</span>
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
                  <p className="text-sm font-medium text-[var(--text-default)]">{item.title}</p>
                  <p className="text-xs text-[var(--text-muted)]">{item.meta}</p>
                </div>
              </div>
              <Badge className={STATUS_CLASS[item.status]}>{item.status}</Badge>
            </li>
          );
        })}
      </ul>
      {warning ? <NoticeCard tone="warning" icon={<AlertCircle size={18} aria-hidden />} title={warning.title} description={warning.description} /> : null}
      {actions}
    </Card>
  );
}
