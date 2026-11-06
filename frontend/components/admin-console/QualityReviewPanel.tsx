import { LibraryBadge, LibraryWarning } from "@/components/admin-console/LibraryStatus";
import { Card } from "@/components/ui/Card";
import type { QualityReviewDetail } from "@/types/api";

function MetaField({ label, value, className }: { label: string; value: string; className?: string }) {
  return (
    <div className={className}>
      <p className="text-2xs font-medium uppercase tracking-wide text-[var(--text-muted)]">{label}</p>
      <p className="mt-0.5 text-sm font-semibold text-[var(--text-default)]">{value}</p>
    </div>
  );
}

/** A practice's metadata and source quality checks, on its own page. */
export function QualityReviewPanel({ review }: { review: QualityReviewDetail }) {
  return (
    <div className="space-y-5">
      <Card className="space-y-4">
        <h2 className="text-sm font-semibold text-[var(--text-default)]">Metadata</h2>
        <div className="grid gap-x-4 gap-y-3 sm:grid-cols-2">
          <MetaField label="Taxonomy" value={review.taxonomy} />
          <MetaField label="Maturity" value={review.maturity} />
          <MetaField label="Practice owner" value={review.practiceOwner} />
          <MetaField label="Approver" value={review.approver} />
          {review.sourceAttribution ? (
            <MetaField label="Source attribution & rights" value={review.sourceAttribution} className="sm:col-span-2" />
          ) : null}
        </div>
      </Card>

      <Card className="space-y-2">
        <h2 className="text-sm font-semibold text-[var(--text-default)]">Source quality checks</h2>
        <ul className="divide-y divide-[var(--surface-border)]">
          {review.sourceQualityChecks.map((check) => (
            <li key={check.id} className="flex items-center justify-between gap-3 py-2.5 text-xs text-[var(--text-default)]">
              <span>{check.label}</span>
              <LibraryBadge tone={check.state === "Passed" ? "success" : "warning"}>{check.state}</LibraryBadge>
            </li>
          ))}
        </ul>
        {review.warning ? <LibraryWarning {...review.warning} /> : null}
      </Card>
    </div>
  );
}
