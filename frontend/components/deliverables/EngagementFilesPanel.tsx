import { ClipboardList, FileText, Presentation } from "lucide-react";

import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import { cn } from "@/lib/utils";
import type { EngagementFile } from "@/types/api";

const ICONS = {
  pptx: Presentation,
  docx: FileText,
  evidence: ClipboardList,
} as const;

const TYPE_LABEL_CLASS: Record<string, string> = {
  pptx: "text-[var(--accent-green-dark)]",
  docx: "text-[#3B596F]",
};

const STATUS_CLASS: Record<string, string> = {
  "Changes requested": "border-[var(--surface-border)] bg-[#FCF3E2] text-[#8C5B12]",
  Draft: "border-[var(--surface-border)] bg-[#F4F5F3] text-[#677067]",
  Approved: "border-[var(--surface-border)] bg-[#EFF6E6] text-[#356B12]",
};

export function EngagementFilesPanel({
  files,
  activeFileId,
  onSelect,
}: {
  files: EngagementFile[];
  activeFileId: string;
  onSelect: (id: string) => void;
}) {
  return (
    <Card className="space-y-3">
      <h2 className="text-base font-semibold text-[var(--text-default)]">Engagement files</h2>
      <ul className="space-y-2">
        {files.map((file) => {
          const Icon = ICONS[file.type];
          const active = file.id === activeFileId;
          return (
            <li key={file.id}>
              <button
                type="button"
                onClick={() => onSelect(file.id)}
                className={cn(
                  "flex w-full flex-col gap-1 rounded-md border p-3 text-left transition",
                  active
                    ? "border-l-2 border-l-[var(--accent-green)] bg-[#EFF6E6] border-y-transparent border-r-transparent"
                    : "border-transparent hover:bg-[var(--surface-muted)]"
                )}
              >
                <span className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wide">
                  <Icon size={14} className="text-[var(--text-muted)]" aria-hidden />
                  <span className={TYPE_LABEL_CLASS[file.type] ?? "text-[var(--text-muted)]"}>{file.type.toUpperCase()}</span>
                </span>
                <span className="text-sm font-semibold text-[var(--text-default)]">{file.name}</span>
                <span className="text-xs text-[var(--text-muted)]">{file.meta}</span>
                {file.status ? (
                  <Badge className={cn("mt-1 w-fit", STATUS_CLASS[file.status])}>{file.status}</Badge>
                ) : null}
              </button>
            </li>
          );
        })}
      </ul>
    </Card>
  );
}
