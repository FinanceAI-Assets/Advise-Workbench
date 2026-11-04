import { FileUp } from "lucide-react";

import { LibraryBadge, LibraryWarning } from "@/components/admin-console/LibraryStatus";
import { Card } from "@/components/ui/Card";
import type { IngestionJobDetail } from "@/types/api";

function JobFact({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-2xs font-medium uppercase tracking-wide text-[var(--text-muted)]">{label}</p>
      <p className="mt-0.5 text-xs font-semibold text-[var(--text-default)]">{value}</p>
    </div>
  );
}

export function IngestionJobPanel({ job }: { job: IngestionJobDetail }) {
  return (
    <Card className="space-y-4">
      <div className="flex items-center justify-between gap-3">
        <h2 className="text-sm font-semibold text-[var(--text-default)]">Latest ingestion job</h2>
        <span className="text-2xs text-[var(--text-muted)]">
          {[job.id.toUpperCase(), job.submittedAt].filter(Boolean).join(" · ")}
        </span>
      </div>

      <div className="flex items-start justify-between gap-3 rounded-md border border-dashed border-[var(--surface-border-strong)] bg-[var(--surface-muted)] px-4 py-3.5">
        <div className="flex min-w-0 items-start gap-3">
          <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md border border-[var(--surface-border)] bg-white text-[var(--text-muted)]">
            <FileUp size={15} aria-hidden />
          </span>
          <div className="min-w-0">
            <p className="truncate text-xs font-semibold text-[var(--text-default)]">{job.filename}</p>
            <p className="text-2xs text-[var(--text-muted)]">{job.meta}</p>
          </div>
        </div>
        <LibraryBadge>{job.status}</LibraryBadge>
      </div>

      <div className="grid gap-4 sm:grid-cols-3">
        <JobFact label="Extraction" value={job.extractionMeta} />
        <JobFact label="Index validation" value={job.indexValidationMeta} />
        <JobFact label="Provenance" value={job.provenanceMeta} />
      </div>

      {job.warning ? <LibraryWarning {...job.warning} /> : null}
    </Card>
  );
}
