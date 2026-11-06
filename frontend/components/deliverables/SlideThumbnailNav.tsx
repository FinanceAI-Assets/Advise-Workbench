import { SlideDecisionMark, type SlideReview } from "@/components/deliverables/SlideDecision";
import { cn } from "@/lib/utils";
import type { Slide } from "@/types/api";

export function SlideThumbnailNav({
  slides,
  activeIndex,
  onSelect,
  decisionOf,
}: {
  slides: Slide[];
  activeIndex: number;
  onSelect: (index: number) => void;
  decisionOf?: SlideReview["decisionOf"];
}) {
  const active = slides[activeIndex];

  // Show a 5-wide window trailing the active slide (matches the design: slide
  // 4 of 12 appears as the 4th of 5 visible tiles, not centered) and clamp to
  // the slide list bounds.
  const windowSize = 5;
  let windowStart = Math.max(0, activeIndex - (windowSize - 2));
  windowStart = Math.min(windowStart, Math.max(0, slides.length - windowSize));
  const visibleSlides = slides.slice(windowStart, windowStart + windowSize);

  return (
    <div className="space-y-3">
      <p className="text-sm text-[var(--text-muted)]">
        Slide {active.index} of {slides.length} · {active.title}
      </p>
      <div className="grid grid-cols-5 gap-2">
        {visibleSlides.map((slide, offset) => {
          const i = windowStart + offset;
          return (
            <button
              key={slide.id}
              type="button"
              onClick={() => onSelect(i)}
              className={cn(
                "rounded-md border p-2 text-left transition",
                i === activeIndex
                  ? "border-[var(--accent-green)] bg-[#EFF6E6]"
                  : "border-[var(--surface-border)] bg-[var(--surface-muted)] hover:bg-white"
              )}
            >
              <div className="flex items-center justify-between gap-1">
                <p className="text-2xs text-[var(--text-muted)]">{String(slide.index).padStart(2, "0")}</p>
                <SlideDecisionMark decision={decisionOf?.(slide.index)} />
              </div>
              <p className="truncate text-xs font-medium text-[var(--text-default)]">{slide.title}</p>
            </button>
          );
        })}
      </div>
    </div>
  );
}
