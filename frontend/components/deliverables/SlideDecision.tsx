import { Check, X } from "lucide-react";

import { Button } from "@/components/ui/Button";
import type { SlideDecision } from "@/hooks/useDeliverables";
import { cn } from "@/lib/utils";
import type { Slide } from "@/types/api";

export type SlideReview = {
  decisionOf: (slideNumber: number) => SlideDecision | undefined;
  onDecide: (slideNumber: number, decision: SlideDecision | null) => void;
  onDecideAll: (slideNumbers: number[], decision: SlideDecision | null) => void;
  locked: boolean;
};

const OPTIONS = [
  { value: "accepted", label: "Accept slide", clear: "Clear acceptance", deck: "Accept PPT", Icon: Check, on: "!border-[#356B12] !bg-[#EFF6E6] !text-[#356B12]" },
  { value: "rejected", label: "Reject slide", clear: "Clear rejection", deck: "Reject PPT", Icon: X, on: "!border-[#A53E37] !bg-[#FBEFEB] !text-[#A53E37]" },
] as const;

/** Accept and reject one slide. Choosing the current decision again clears it. */
export function SlideDecisionButtons({ slideNumber, review }: { slideNumber: number; review: SlideReview }) {
  const current = review.decisionOf(slideNumber);
  return (
    <div className="flex items-center gap-1.5">
      {OPTIONS.map(({ value, label, clear, Icon, on }) => {
        const active = current === value;
        const name = active ? clear : label;
        return (
          <Button
            key={value}
            variant="secondary"
            type="button"
            aria-label={name}
            aria-pressed={active}
            title={review.locked ? "Slide decisions are locked after approval" : name}
            disabled={review.locked}
            onClick={() => review.onDecide(slideNumber, active ? null : value)}
            className={cn("inline-flex h-8 w-8 items-center justify-center p-0", active && on)}
          >
            <Icon size={16} aria-hidden />
          </Button>
        );
      })}
    </div>
  );
}

/**
 * Accept or reject the whole deck, which sets the decision on every slide. A button shows as chosen only while
 * every slide has that decision, and choosing it again clears them all.
 */
export function DeckDecisionButtons({ slides, review }: { slides: Slide[]; review: SlideReview }) {
  const numbers = slides.map((slide) => slide.index);
  const countOf = (decision: SlideDecision) => numbers.filter((n) => review.decisionOf(n) === decision).length;
  const accepted = countOf("accepted");
  const rejected = countOf("rejected");
  return (
    <div className="flex flex-wrap items-center justify-between gap-2 border-t border-[var(--surface-border)] pt-3">
      <p className="text-xs text-[var(--text-muted)]" aria-live="polite">
        <span className="font-semibold text-[var(--text-default)]">Whole PPT</span> · {accepted} accepted · {rejected} rejected ·{" "}
        {numbers.length - accepted - rejected} undecided
      </p>
      <div className="flex items-center gap-2">
        {OPTIONS.map(({ value, clear, deck, Icon, on }) => {
          const active = numbers.length > 0 && countOf(value) === numbers.length;
          return (
            <Button
              key={value}
              variant="secondary"
              type="button"
              aria-pressed={active}
              title={review.locked ? "Slide decisions are locked after approval" : active ? `${clear} on every slide` : `${deck}: applies to every slide`}
              disabled={review.locked}
              onClick={() => review.onDecideAll(numbers, active ? null : value)}
              className={cn("inline-flex items-center gap-2 whitespace-nowrap text-sm", active && on)}
            >
              <Icon size={16} aria-hidden />
              {deck}
            </Button>
          );
        })}
      </div>
    </div>
  );
}

/** Small marker for a slide in a list, so decisions can be seen without opening each slide. */
export function SlideDecisionMark({ decision }: { decision: SlideDecision | undefined }) {
  if (!decision) return null;
  const accepted = decision === "accepted";
  const Icon = accepted ? Check : X;
  return (
    <span role="img" aria-label={accepted ? "Accepted" : "Rejected"} className={cn("shrink-0", accepted ? "text-[#356B12]" : "text-[#A53E37]")}>
      <Icon size={14} aria-hidden />
    </span>
  );
}
