"use client";

import { Check, ChevronLeft, ChevronRight, X } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/Button";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { Textarea } from "@/components/ui/Textarea";
import { ErrorNote } from "@/components/workbench/PageFrame";
import type { SlideDecision } from "@/hooks/useDeliverables";
import type { DeckDesignReview } from "@/hooks/usePhase5Review";
import { cn } from "@/lib/utils";
import type { Slide } from "@/types/api";

export type SlideReview = {
  decisionOf: (slideNumber: number) => SlideDecision | undefined;
  onDecide: (slideNumber: number, decision: SlideDecision | null) => void;
  onDecideAll: (slideNumbers: number[], decision: SlideDecision | null) => void;
  locked: boolean;
  /** Set while the run has a design review: the deck buttons then approve the run or send the deck back. */
  designReview?: DeckDesignReview | null;
};

const OPTIONS = [
  { value: "accepted", label: "Accept slide", clear: "Clear acceptance", deck: "Accept PPT", Icon: Check, on: "!border-[#356B12] !bg-[#EFF6E6] !text-[#356B12]" },
  { value: "rejected", label: "Reject slide", clear: "Clear rejection", deck: "Reject PPT", Icon: X, on: "!border-[#A53E37] !bg-[#FBEFEB] !text-[#A53E37]" },
] as const;

const SQUARE = "inline-flex h-9 w-9 items-center justify-center p-0";

/**
 * Below the slide: previous and next arrows around its accept and reject buttons. Accepting moves on to the
 * next slide; choosing the current decision again clears it. Without `review` only the arrows show.
 */
export function SlideReviewBar({
  index,
  total,
  onSelect,
  review,
}: {
  /** Position of the slide on screen, from 0. */
  index: number;
  total: number;
  onSelect: (index: number) => void;
  review?: SlideReview;
}) {
  const slideNumber = index + 1;
  const current = review?.decisionOf(slideNumber);
  const atEnd = index >= total - 1;

  function decide(value: SlideDecision) {
    if (!review) return;
    const active = current === value;
    review.onDecide(slideNumber, active ? null : value);
    if (value === "accepted" && !active && !atEnd) onSelect(index + 1);
  }

  return (
    <div className="flex items-center justify-center gap-2">
      <Button
        variant="secondary"
        type="button"
        aria-label="Previous slide"
        title="Previous slide"
        disabled={index === 0}
        onClick={() => onSelect(index - 1)}
        className={SQUARE}
      >
        <ChevronLeft size={18} aria-hidden />
      </Button>
      {review
        ? OPTIONS.map(({ value, label, clear, Icon, on }) => {
            const active = current === value;
            const name = active ? clear : value === "accepted" && !atEnd ? `${label} and go to the next one` : label;
            return (
              <Button
                key={value}
                variant="secondary"
                type="button"
                aria-label={name}
                aria-pressed={active}
                title={review.locked ? "Slide decisions are locked after approval" : name}
                disabled={review.locked}
                onClick={() => decide(value)}
                className={cn(SQUARE, active && on)}
              >
                <Icon size={18} aria-hidden />
              </Button>
            );
          })
        : null}
      <Button
        variant="secondary"
        type="button"
        aria-label="Next slide"
        title="Next slide"
        disabled={atEnd}
        onClick={() => onSelect(index + 1)}
        className={SQUARE}
      >
        <ChevronRight size={18} aria-hidden />
      </Button>
    </div>
  );
}

/**
 * Accept or reject the whole deck after a confirmation. Once any slide is rejected the deck can no longer be
 * accepted, only rejected.
 *
 * While the run waits in design review the buttons answer it: Accept PPT approves the deck (the run moves on once
 * every artifact is approved), and Reject PPT sends it back with feedback, rebuilding only the slides marked
 * rejected (or every slide when none or all are). Otherwise they only mark every slide, and choosing a chosen one again clears them all.
 */
export function DeckDecisionButtons({ slides, review }: { slides: Slide[]; review: SlideReview }) {
  const [confirming, setConfirming] = useState<SlideDecision | null>(null);
  const [feedback, setFeedback] = useState("");
  const numbers = slides.map((slide) => slide.index);
  const countOf = (decision: SlideDecision) => numbers.filter((n) => review.decisionOf(n) === decision).length;
  const accepted = countOf("accepted");
  const rejected = countOf("rejected");
  const rejectedSlides = numbers.filter((n) => review.decisionOf(n) === "rejected");
  const design = review.designReview ?? null;
  const live = design?.waiting && !design.approved ? design : null;
  const partial = rejectedSlides.length > 0 && rejectedSlides.length < numbers.length;

  const dialog =
    confirming === "accepted"
      ? {
          title: live ? "Approve the deck?" : "Accept the whole deck?",
          description: live
            ? `All ${numbers.length} slides will be marked accepted and deck ${live.version} approved. This cannot be undone.`
            : `All ${numbers.length} slides will be marked accepted.`,
          confirmLabel: "Accept PPT",
        }
      : live
        ? {
            title: "Send the deck back?",
            description: partial
              ? `Slides ${rejectedSlides.join(", ")} will be regenerated; the other ${numbers.length - rejectedSlides.length} are kept as they are.`
              : `The whole deck (${numbers.length} slides) will be regenerated.`,
            confirmLabel: "Reject PPT",
          }
        : {
            title: "Reject the whole deck?",
            description: `All ${numbers.length} slides will be marked rejected, including the ${accepted} you accepted.`,
            confirmLabel: "Reject PPT",
          };

  async function confirm() {
    if (!confirming) return;
    try {
      if (live && confirming === "accepted") {
        await live.approve();
        review.onDecideAll(numbers, "accepted");
      } else if (live) {
        await live.reject(partial ? rejectedSlides : null, feedback);
        // The rebuilt slides are new: their old decisions no longer apply.
        review.onDecideAll(partial ? rejectedSlides : numbers, null);
      } else {
        review.onDecideAll(numbers, confirming);
      }
    } catch {
      // The request failed: nothing changes, and the error is shown below.
    } finally {
      setConfirming(null);
      setFeedback("");
    }
  }

  return (
    <div className="space-y-2 border-t border-[var(--surface-border)] pt-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-xs text-[var(--text-muted)]" aria-live="polite">
          <span className="font-semibold text-[var(--text-default)]">Whole PPT</span> · {accepted} accepted · {rejected} rejected ·{" "}
          {numbers.length - accepted - rejected} undecided
        </p>
        <div className="flex items-center gap-2">
          {OPTIONS.map(({ value, clear, deck, Icon, on }) => {
            const active = numbers.length > 0 && countOf(value) === numbers.length;
            const blocked =
              design?.regenerating
                ? "The deck is being regenerated"
                : value === "accepted" && rejected > 0
                  ? "A slide is rejected, so the deck can only be rejected"
                  : value === "rejected" && live?.rejectBlocked
                    ? live.rejectBlocked
                    : null;
            const title = review.locked
              ? "Slide decisions are locked after approval"
              : blocked ?? (active && !live ? `${clear} on every slide` : `${deck}: applies to every slide`);
            return (
              <Button
                key={value}
                variant="secondary"
                type="button"
                aria-pressed={active}
                title={title}
                disabled={review.locked || Boolean(blocked) || Boolean(live?.busy)}
                onClick={() => (active && !live ? review.onDecideAll(numbers, null) : setConfirming(value))}
                className={cn("inline-flex items-center gap-2 whitespace-nowrap text-sm", active && on)}
              >
                <Icon size={16} aria-hidden />
                {deck}
              </Button>
            );
          })}
        </div>
      </div>
      {design?.approved ? <p className="text-xs text-[#356B12]">Deck {design.version} approved.</p> : null}
      <ErrorNote error={design?.error} />
      {confirming ? (
        <ConfirmDialog {...dialog} busy={Boolean(live?.busy)} onCancel={() => setConfirming(null)} onConfirm={() => void confirm()}>
          {live && confirming === "rejected" ? (
            <label className="grid gap-1.5 text-2xs font-semibold uppercase tracking-wide text-[var(--text-muted)]">
              What should change (optional)
              <Textarea
                rows={3}
                value={feedback}
                onChange={(e) => setFeedback(e.target.value)}
                placeholder="For example: tighten the layout of the summary slide"
              />
            </label>
          ) : null}
        </ConfirmDialog>
      ) : null}
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
