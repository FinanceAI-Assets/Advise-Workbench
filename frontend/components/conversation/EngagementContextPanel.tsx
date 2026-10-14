import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import type { EngagementContextSummary } from "@/types/api";

export function EngagementContextPanel({ context }: { context: EngagementContextSummary }) {
  return (
    <Card className="space-y-3">
      <h2 className="text-base font-semibold text-[var(--text-default)]">Engagement context</h2>
      <Badge className="border-[var(--surface-border)] bg-[var(--surface-muted)] text-[var(--text-muted)]">
        {context.classification}
      </Badge>
      <div>
        <p className="font-semibold text-[var(--text-default)]">{context.name}</p>
        <p className="text-sm text-[var(--text-muted)]">{context.description}</p>
      </div>
      <div>
        <p className="text-2xs font-semibold uppercase tracking-wide text-[var(--text-muted)]">Engagement lead</p>
        <p className="text-sm font-semibold text-[var(--text-default)]">{context.lead}</p>
      </div>
      <p className="border-t border-[var(--surface-border)] pt-3 text-xs text-[var(--text-muted)]">{context.teamNote}</p>
    </Card>
  );
}
