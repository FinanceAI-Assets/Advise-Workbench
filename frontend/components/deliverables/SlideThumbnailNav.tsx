import { Button } from "@/components/ui/Button";
import { cn } from "@/lib/utils";
import type { Slide } from "@/types/api";

export function SlideThumbnailNav({
  slides,
  activeIndex,
  onSelect,
}: {
  slides: Slide[];
  activeIndex: number;
  onSelect: (index: number) => void;
}) {
  const active = slides[activeIndex];
  const atStart = activeIndex === 0;
  const atEnd = activeIndex === slides.length - 1;

  // Show a 5-wide window trailing the active slide (matches the design: slide
  // 4 of 12 appears as the 4th of 5 visible tiles, not centered) and clamp to
  // the slide list bounds.
  const windowSize = 5;
  let windowStart = Math.max(0, activeIndex - (windowSize - 2));
  windowStart = Math.min(windowStart, Math.max(0, slides.length - windowSize));
  const visibleSlides = slides.slice(windowStart, windowStart + windowSize);

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-sm text-[var(--text-muted)]">
          Slide {active.index} of {slides.length} · {active.title}
        </p>
        <div className="flex items-center gap-2">
          <Button
            variant="secondary"
            type="button"
            className="whitespace-nowrap text-sm"
            disabled={atStart}
            onClick={() => onSelect(Math.max(0, activeIndex - 1))}
          >
            Previous
          </Button>
          <Button
            variant="secondary"
            type="button"
            className="whitespace-nowrap text-sm"
            disabled={atEnd}
            onClick={() => onSelect(Math.min(slides.length - 1, activeIndex + 1))}
          >
            Next
          </Button>
        </div>
      </div>
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
              <p className="text-2xs text-[var(--text-muted)]">{String(slide.index).padStart(2, "0")}</p>
              <p className="truncate text-xs font-medium text-[var(--text-default)]">{slide.title}</p>
            </button>
          );
        })}
      </div>
    </div>
  );
}
