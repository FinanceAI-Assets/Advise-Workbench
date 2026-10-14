import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import type { PolicyControlItem } from "@/types/api";

export function PolicyControlsPanel({
  items,
  policyCode,
  exportPermissionsNote,
}: {
  items: PolicyControlItem[];
  policyCode: string;
  exportPermissionsNote: string;
}) {
  return (
    <Card className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-base font-semibold text-[var(--text-default)]">Active policy controls</h2>
        <span className="text-xs text-[var(--text-muted)]">{policyCode}</span>
      </div>
      <ul className="space-y-3">
        {items.map((item) => (
          <li key={item.id} className="flex items-center justify-between text-sm">
            <span className="text-[var(--text-default)]">{item.label}</span>
            <Badge className="border-[var(--surface-border)] bg-[#EFF6E6] text-[#356B12]">{item.state}</Badge>
          </li>
        ))}
      </ul>
      <div className="border-t border-[var(--surface-border)] pt-3">
        <p className="text-sm font-semibold text-[var(--text-default)]">Export permissions</p>
        <p className="mt-1 text-xs text-[var(--text-muted)]">{exportPermissionsNote}</p>
      </div>
    </Card>
  );
}
