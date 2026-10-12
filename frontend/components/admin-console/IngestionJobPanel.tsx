import { AlertCircle, FileUp } from "lucide-react";

import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import { NoticeCard } from "@/components/ui/NoticeCard";
import type { IngestionJobDetail } from "@/types/api";

export function IngestionJobPanel({ job }: { job: IngestionJobDetail }) {
  return (
    <Card className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-base font-semibold text-[var(--text-default)]">Latest ingestion job</h2>
        <span className="text-xs text-[var(--text-muted)]">{job.id.toUpperCase()}</span>
      </div>

      <div className="flex items-start justify-between gap-3">
        <div className="flex items-start gap-3">
          <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-[var(--surface-muted)] text-[var(--text-muted)]">
            <FileUp size={16} aria-hidden />
          </span>
          <div>
            <p className="text-sm font-medium text-[var(--text-default)]">{job.filename}</p>
            <p className="text-xs text-[var(--text-muted)]">{job.meta}</p>
          </div>
        </div>
        <Badge className="shrink-0 border-[var(--surface-border)] bg-[#EFF6E6] text-[#356B12]">{job.status}</Badge>
      </div>

      <div className="grid gap-4 border-t border-[var(--surface-border)] pt-4 sm:grid-cols-3">
        <div>
          <p className="text-2xs font-semibold uppercase tracking-wide text-[var(--text-muted)]">Extraction</p>
          <p className="text-sm font-medium text-[var(--text-default)]">{job.extractionMeta}</p>
        </div>
        <div>
          <p className="text-2xs font-semibold uppercase tracking-wide text-[var(--text-muted)]">Index validation</p>
          <p className="text-sm font-medium text-[var(--text-default)]">{job.indexValidationMeta}</p>
        </div>
        <div>
          <p className="text-2xs font-semibold uppercase tracking-wide text-[var(--text-muted)]">Provenance</p>
          <p className="text-sm font-medium text-[var(--text-default)]">{job.provenanceMeta}</p>
        </div>
      </div>

      {job.warning ? (
        <NoticeCard tone="warning" icon={<AlertCircle size={18} aria-hidden />} title={job.warning.title} description={job.warning.description} />
      ) : null}
    </Card>
  );
}
