import { Card } from "@/components/ui/Card";
import { cn } from "@/lib/utils";
import type { Slide } from "@/types/api";

/** PowerPoint tab: every slide as a numbered list entry, with how many claims each one carries. */
export function SlideNavigator({
  slides,
  activeIndex,
  claimCounts,
  onSelect,
}: {
  slides: Slide[];
  activeIndex: number;
  claimCounts: Record<number, number>;
  onSelect: (index: number) => void;
}) {
  return (
    <Card className="space-y-2">
      <h2 className="text-base font-semibold text-[var(--text-default)]">Slide navigator</h2>
      <ul className="max-h-[560px] space-y-1 overflow-y-auto">
        {slides.map((slide, i) => {
          const active = i === activeIndex;
          const claims = claimCounts[i] ?? 0;
          return (
            <li key={slide.id}>
              <button
                type="button"
                onClick={() => onSelect(i)}
                aria-current={active ? "true" : undefined}
                className={cn(
                  "w-full rounded-md border-l-2 px-2 py-2 text-left transition",
                  active
                    ? "border-l-[var(--accent-green)] bg-[#EFF6E6]"
                    : "border-l-transparent hover:bg-[var(--surface-muted)]"
                )}
              >
                <span className="flex items-center gap-2 text-sm font-semibold text-[var(--text-default)]">
                  <span className="truncate">
                    {String(slide.index).padStart(2, "0")} {slide.title}
                  </span>
                  {claims ? (
                    <span className="shrink-0 text-2xs font-medium text-[var(--accent-green-dark)]">
                      {claims} claim{claims === 1 ? "" : "s"}
                    </span>
                  ) : null}
                </span>
                <span className="block text-xs text-[var(--text-muted)]">{active ? "Selected slide" : `Slide ${slide.index}`}</span>
              </button>
            </li>
          );
        })}
      </ul>
    </Card>
  );
}
