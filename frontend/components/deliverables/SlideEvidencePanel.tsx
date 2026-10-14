import { FileText, Library } from "lucide-react";

import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import type { SlideEvidenceLink } from "@/types/api";

const ICONS = {
  library: Library,
  doc: FileText,
} as const;

export function SlideEvidencePanel({ links }: { links: SlideEvidenceLink[] }) {
  return (
    <Card className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-base font-semibold text-[var(--text-default)]">Evidence linked to this slide</h2>
        <span className="text-xs text-[var(--text-muted)]">{links.length} sources</span>
      </div>
      <ul className="space-y-3">
        {links.map((link) => {
          const Icon = ICONS[link.icon];
          return (
            <li key={link.id} className="flex items-start justify-between gap-3">
              <div className="flex items-start gap-3">
                <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-[var(--surface-muted)] text-[var(--text-muted)]">
                  <Icon size={16} aria-hidden />
                </span>
                <div>
                  <p className="text-sm font-medium text-[var(--text-default)]">
                    [{link.index}] {link.label}
                  </p>
                  <p className="text-xs text-[var(--text-muted)]">{link.description}</p>
                </div>
              </div>
              {link.verified ? (
                <Badge className="shrink-0 border-[var(--surface-border)] bg-[#EFF6E6] text-[#356B12]">Verified</Badge>
              ) : null}
            </li>
          );
        })}
      </ul>
    </Card>
  );
}
