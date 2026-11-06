import { ArrowLeft, ArrowRight, Check } from "lucide-react";

import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { cn } from "@/lib/utils";
import type { EngagementStep } from "@/types/api";

const MARKER_CLASS: Record<EngagementStep["status"], string> = {
  complete: "border-[var(--accent-green)] bg-[var(--accent-green)] text-white",
  "in-progress": "border-[var(--accent-green)] bg-white text-[var(--accent-green-dark)]",
  upcoming: "border-[var(--surface-border-strong)] bg-white text-[var(--text-muted)]",
};

/**
 * The five library ingestion steps of one source: numbered markers joined by a progress line, with each step's label
 * and status centred below. The step on screen is solid green with a halo; finished steps show a tick and fill the
 * line behind them. Each step opens its view.
 */
export function PipelineStepper({
  steps,
  activeId,
  onSelect,
}: {
  steps: EngagementStep[];
  /** The highlighted step: the one on screen, or on the practice page the one the practice has reached. */
  activeId: string;
  onSelect: (stepId: string) => void;
}) {
  return (
    <Card className="overflow-x-auto px-4 py-5">
      <ol className="flex min-w-[720px] items-start" aria-label="Library pipeline">
        {steps.map((step, index) => {
          const active = step.id === activeId;
          const complete = step.status === "complete";
          return (
            <li key={step.id} className="relative flex flex-1 justify-center">
              {/* The line to the next step, from this marker's edge to the next one's; green once this step is done. */}
              {index < steps.length - 1 ? (
                <span
                  aria-hidden
                  className="absolute left-[calc(50%+24px)] right-[calc(-50%+24px)] top-[17px] h-[3px] overflow-hidden rounded-full bg-[var(--surface-border)]"
                >
                  <span className={cn("block h-full rounded-full bg-[var(--accent-green)] transition-all duration-500", complete ? "w-full" : "w-0")} />
                </span>
              ) : null}
              <button
                type="button"
                onClick={() => onSelect(step.id)}
                aria-current={active ? "step" : undefined}
                className="group flex max-w-[160px] flex-col items-center gap-2 rounded-lg px-2 text-center focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-[var(--accent-green)]"
              >
                <span
                  className={cn(
                    "relative z-10 flex h-9 w-9 items-center justify-center rounded-full border-2 text-sm font-semibold transition-all duration-200",
                    active
                      ? "border-[var(--accent-green)] bg-[var(--accent-green)] text-white shadow-[0_0_0_5px_#EFF6E6]"
                      : cn(MARKER_CLASS[step.status], "group-hover:shadow-[0_0_0_4px_var(--surface-muted)]")
                  )}
                >
                  {complete && !active ? <Check size={16} strokeWidth={3} aria-label="Complete" /> : index + 1}
                </span>
                <span>
                  <span
                    className={cn(
                      "block text-sm font-semibold leading-5",
                      active ? "text-[var(--accent-green-dark)]" : step.status === "upcoming" ? "text-[var(--text-muted)]" : "text-[var(--text-default)]"
                    )}
                  >
                    {step.label}
                  </span>
                  <span
                    className={cn(
                      "mt-0.5 inline-block text-2xs",
                      active ? "font-medium text-[var(--accent-green-dark)]" : complete ? "text-[var(--accent-green-dark)]" : "text-[var(--text-muted)]"
                    )}
                  >
                    {step.helper}
                  </span>
                </span>
              </button>
            </li>
          );
        })}
      </ol>
    </Card>
  );
}

/** Moves between the pipeline steps; the first and last steps lead back to the practice. */
export function StepperFooter({
  position,
  total,
  onBack,
  backLabel,
  onNext,
  nextLabel,
  nextDisabled = false,
}: {
  position: number;
  total: number;
  onBack: () => void;
  backLabel: string;
  onNext: () => void;
  nextLabel: string;
  /** Set while the next step has nothing to show yet, such as before a new source is uploaded. */
  nextDisabled?: boolean;
}) {
  return (
    <Card className="flex flex-wrap items-center justify-between gap-3 p-3">
      <Button type="button" variant="secondary" className="flex items-center gap-2 whitespace-nowrap text-sm" onClick={onBack}>
        <ArrowLeft size={16} aria-hidden />
        {backLabel}
      </Button>
      <span className="text-xs text-[var(--text-muted)]">
        Step {position} of {total}
      </span>
      <Button type="button" disabled={nextDisabled} className="flex items-center gap-2 whitespace-nowrap text-sm" onClick={onNext}>
        {nextLabel}
        <ArrowRight size={16} aria-hidden />
      </Button>
    </Card>
  );
}
