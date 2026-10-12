import { AlertTriangle, Download } from "lucide-react";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import type { DeliverablesDetail } from "@/types/api";

const STATUS_CLASS: Record<string, string> = {
  "Changes requested": "border-[var(--surface-border)] bg-[#FCF3E2] text-[#8C5B12]",
  Draft: "border-[var(--surface-border)] bg-[#F4F5F3] text-[#677067]",
  Approved: "border-[var(--surface-border)] bg-[#EFF6E6] text-[#356B12]",
};

export function WordArtifactPanel({ docx }: { docx: DeliverablesDetail["docx"] }) {
  return (
    <Card className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-base font-semibold text-[var(--text-default)]">Word artifact</h2>
        <span className="text-xs text-[var(--text-muted)]">DOCX</span>
      </div>
      <p className="font-semibold text-[var(--text-default)]">{docx.name}</p>
      <div className="flex items-center justify-between">
        <Badge className={STATUS_CLASS[docx.status]}>{docx.status}</Badge>
        <span className="text-xs text-[var(--text-muted)]">{docx.versionLabel}</span>
      </div>

      <div className="space-y-3 rounded-lg border border-[var(--surface-border)] bg-white p-4">
        <p className="text-2xs font-semibold uppercase tracking-wide text-[var(--text-muted)]">{docx.preview.breadcrumb}</p>
        <h3 className="text-lg font-semibold text-[var(--text-default)]">{docx.preview.title}</h3>
        <p className="text-xs text-[var(--text-muted)]">{docx.preview.meta}</p>
        <div className="space-y-3 border-t border-[var(--surface-border)] pt-3">
          {docx.preview.sections.map((section) => (
            <div key={section.heading}>
              <p className="text-sm font-semibold text-[var(--text-default)]">{section.heading}</p>
              <p className="text-xs text-[var(--text-muted)]">{section.body}</p>
            </div>
          ))}
        </div>
        <div className="flex items-center justify-between border-t border-[var(--surface-border)] pt-3 text-xs text-[var(--text-muted)]">
          <span>{docx.preview.footerMeta}</span>
          <span>{docx.preview.pageLabel}</span>
        </div>
      </div>

      <p className="text-xs text-[var(--text-muted)]">{docx.citationSummary}</p>
      <Button variant="secondary" type="button" disabled className="flex w-full items-center justify-center gap-2 text-sm">
        <Download size={16} aria-hidden />
        Download DOCX
      </Button>

      {docx.exportWarning ? (
        <div className="flex items-start gap-2 rounded-md border border-[#F3E2C0] bg-[#FCF3E2] p-3">
          <AlertTriangle size={16} className="mt-0.5 shrink-0 text-[#8C5B12]" aria-hidden />
          <div>
            <p className="text-sm font-semibold text-[#8C5B12]">{docx.exportWarning.title}</p>
            <p className="text-xs text-[#8C5B12]">{docx.exportWarning.description}</p>
          </div>
        </div>
      ) : null}

      <p className="text-xs text-[var(--text-muted)]">{docx.generatedFootnote}</p>
    </Card>
  );
}
