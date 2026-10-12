import { Card } from "@/components/ui/Card";
import type { EngagementBrief } from "@/types/api";

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-2xs font-semibold uppercase tracking-wide text-[var(--text-muted)]">{label}</p>
      <p className="text-sm font-medium text-[var(--text-default)]">{value}</p>
    </div>
  );
}

export function EngagementBriefCard({ brief }: { brief: EngagementBrief }) {
  return (
    <Card className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-base font-semibold text-[var(--text-default)]">Engagement brief</h2>
        {brief.updated ? <span className="text-xs text-[var(--text-muted)]">{brief.updated}</span> : null}
      </div>
      <p className="text-base font-medium text-[var(--text-default)]">{brief.summary}</p>
      {brief.context ? <p className="text-sm text-[var(--text-muted)]">{brief.context}</p> : null}
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Sponsor objective" value={brief.sponsorObjective} />
        <Field label="Scope" value={brief.scope} />
        <Field label="Success measures" value={brief.successMeasures} />
        <Field label="Classification" value={brief.classification} />
      </div>
    </Card>
  );
}
