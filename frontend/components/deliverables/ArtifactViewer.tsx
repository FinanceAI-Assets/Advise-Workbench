"use client";

import { Download } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { SlideCanvas } from "@/components/deliverables/SlideCanvas";
import { DeckDecisionButtons, SlideReviewBar, type SlideReview } from "@/components/deliverables/SlideDecision";
import { SlideThumbnailNav } from "@/components/deliverables/SlideThumbnailNav";
import type { DeliverablesDetail } from "@/types/api";

export function ArtifactViewer({
  pptx,
  getSlideDetail,
  onSlideChange,
  onDownload,
  slideReview,
}: {
  pptx: DeliverablesDetail["pptx"];
  // Optional: when the caller holds the raw pptx_slides.json array (real
  // run data), it supplies this to resolve full content for any slide the
  // user browses to, not just the one `pptx.slideDetail` was built for.
  getSlideDetail?: (index: number) => DeliverablesDetail["pptx"]["slideDetail"];
  // Optional: lets the caller (e.g. the Deliverables page) keep its own
  // evidence/sources panel in sync with whichever slide is on screen, since
  // the selected index otherwise lives only in this component's state.
  onSlideChange?: (index: number) => void;
  // Download action; the button is disabled until its handler is supplied.
  onDownload?: () => void;
  // Accept and reject buttons below the slide, shown when the caller supplies it.
  slideReview?: SlideReview;
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

  function selectSlide(index: number) {
    setActiveIndex(index);
    onSlideChange?.(index);
  }

  return (
    <Card className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-base font-semibold text-[var(--text-default)]">{pptx.name}</h2>
        <span className="text-xs text-[var(--text-muted)]">{pptx.versionLabel}</span>
      </div>

      <div className="flex justify-end">
        <Button
          variant="secondary"
          type="button"
          disabled={!onDownload}
          onClick={onDownload}
          title={onDownload ? undefined : "Available after the deck is accepted"}
          className="flex items-center gap-2 whitespace-nowrap text-sm"
        >
          <Download size={16} aria-hidden />
          Download PPTX
        </Button>
      </div>

      <SlideCanvas slide={slide} />

      <SlideReviewBar index={activeIndex} total={pptx.slides.length} onSelect={selectSlide} review={slideReview} />

      <SlideThumbnailNav slides={pptx.slides} activeIndex={activeIndex} onSelect={selectSlide} decisionOf={slideReview?.decisionOf} />

      {slideReview ? <DeckDecisionButtons slides={pptx.slides} review={slideReview} /> : null}
    </Card>
  );
}
