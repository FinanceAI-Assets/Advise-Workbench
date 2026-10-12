"use client";

import { ClipboardCheck, Download } from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { SlideCanvas } from "@/components/deliverables/SlideCanvas";
import { SlideThumbnailNav } from "@/components/deliverables/SlideThumbnailNav";
import type { DeliverablesDetail } from "@/types/api";

const STATUS_CLASS: Record<string, string> = {
  "Changes requested": "border-[var(--surface-border)] bg-[#FCF3E2] text-[#8C5B12]",
  Draft: "border-[var(--surface-border)] bg-[#F4F5F3] text-[#677067]",
  Approved: "border-[var(--surface-border)] bg-[#EFF6E6] text-[#356B12]",
};

export function ArtifactViewer({
  pptx,
  getSlideDetail,
}: {
  pptx: DeliverablesDetail["pptx"];
  // Optional: when the caller holds the raw pptx_slides.json array (real
  // run data), it supplies this to resolve full content for any slide the
  // user browses to, not just the one `pptx.slideDetail` was built for.
  getSlideDetail?: (index: number) => DeliverablesDetail["pptx"]["slideDetail"];
}) {
  const [activeIndex, setActiveIndex] = useState(pptx.activeSlideIndex);
  const activeSlide = pptx.slides[activeIndex];
  const slide =
    activeIndex === pptx.activeSlideIndex
      ? pptx.slideDetail
      : getSlideDetail
        ? getSlideDetail(activeIndex)
        : {
            ...pptx.slideDetail,
            headline: activeSlide.title,
            phases: [],
            sources: "Full detail not available for this slide.",
            pageLabel: `${String(activeSlide.index).padStart(2, "0")} / ${pptx.slides.length}`,
          };

  return (
    <Card className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-base font-semibold text-[var(--text-default)]">{pptx.name}</h2>
        <span className="text-xs text-[var(--text-muted)]">{pptx.versionLabel}</span>
      </div>

      <div className="flex flex-wrap items-center justify-between gap-2">
        <Badge className={STATUS_CLASS[pptx.status]}>{pptx.status}</Badge>
        <div className="flex items-center gap-2">
          <Button variant="secondary" type="button" className="flex items-center gap-2 whitespace-nowrap text-sm">
            <ClipboardCheck size={16} aria-hidden />
            Open review
          </Button>
          <Button variant="secondary" type="button" disabled className="flex items-center gap-2 whitespace-nowrap text-sm">
            <Download size={16} aria-hidden />
            Download PPTX
          </Button>
        </div>
      </div>

      <SlideCanvas slide={slide} />

      <SlideThumbnailNav slides={pptx.slides} activeIndex={activeIndex} onSelect={setActiveIndex} />
    </Card>
  );
}
