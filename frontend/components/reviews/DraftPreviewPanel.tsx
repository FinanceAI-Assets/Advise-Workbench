import { ArrowUpRight } from "lucide-react";

import { SlideCanvas } from "@/components/deliverables";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import type { SlideDetail } from "@/types/api";

export function DraftPreviewPanel({
  slide,
  versionLabel,
  commentCount,
}: {
  slide: SlideDetail;
  versionLabel: string;
  commentCount: number;
}) {
  return (
    <Card className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-base font-semibold text-[var(--text-default)]">Draft preview</h2>
        <span className="text-xs text-[var(--text-muted)]">
          Slide {slide.pageLabel} · {versionLabel}
        </span>
      </div>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <Badge className="border-[var(--surface-border)] bg-[#FCF3E2] text-[#8C5B12]">Changes requested</Badge>
        <Button variant="secondary" type="button" className="flex items-center gap-2 whitespace-nowrap text-sm">
          <ArrowUpRight size={16} aria-hidden />
          Open full artifact
        </Button>
      </div>

      <SlideCanvas slide={slide} />

      <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-[var(--text-muted)]">
        <span>{commentCount} comments on this slide · Source links preserved</span>
        <Badge className="border-[var(--surface-border)] bg-[var(--surface-muted)] text-[var(--text-muted)]">
          AI-assisted draft
        </Badge>
      </div>
    </Card>
  );
}
