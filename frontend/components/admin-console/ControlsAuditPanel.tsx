import type { ReactNode } from "react";
import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import type { ControlAuditItem } from "@/types/api";

export function ControlsAuditPanel({ items, auditEvent, actions }: { items: ControlAuditItem[]; auditEvent: string; actions?: ReactNode }) {
  return (
    <Card className="space-y-4">
      <h2 className="text-base font-semibold text-[var(--text-default)]">Controls &amp; audit</h2>
      <ul className="space-y-3">
        {items.map((item) => (
          <li key={item.id} className="flex items-center justify-between">
            <span className="text-sm text-[var(--text-default)]">{item.label}</span>
            <Badge className="border-[var(--surface-border)] bg-[#EFF6E6] text-[#356B12]">{item.state}</Badge>
          </li>
        ))}
      </ul>
      <p className="border-t border-[var(--surface-border)] pt-3 text-xs text-[var(--text-muted)]">{auditEvent}</p>
      {actions}
    </Card>
  );
}
