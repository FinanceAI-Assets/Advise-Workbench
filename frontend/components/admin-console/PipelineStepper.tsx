import { ArrowLeft, ArrowRight, Check } from "lucide-react";

import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { cn } from "@/lib/utils";
import type { EngagementStep } from "@/types/api";

const MARKER_CLASS: Record<EngagementStep["status"], string> = {
  complete: "border-[var(--accent-green)] bg-[var(--accent-green)] text-white",
  "in-progress": "border-[var(--accent-green)] bg-[#EFF6E6] text-[var(--accent-green-dark)]",
  upcoming: "border-[var(--surface-border-strong)] bg-white text-[var(--text-muted)]",
};

/** The five library ingestion steps, numbered and joined in one row; each step opens its view. */
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
    <Card className="overflow-x-auto p-3">
      <ol className="flex min-w-[760px] items-start" aria-label="Library pipeline">
        {steps.map((step, index) => {
          const active = step.id === activeId;
          return (
            <li key={step.id} className="flex flex-1 items-start last:flex-none">
              <button
                type="button"
                onClick={() => onSelect(step.id)}
                aria-current={active ? "step" : undefined}
                className={cn(
                  "flex items-start gap-2.5 rounded-md border px-2 py-1.5 text-left transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--accent-green)]",
                  active ? "border-[var(--accent-green)] bg-[#EFF6E6]" : "border-transparent hover:bg-[var(--surface-muted)]"
                )}
              >
                <span
                  className={cn(
                    "flex h-7 w-7 shrink-0 items-center justify-center rounded-full border text-xs font-semibold",
                    MARKER_CLASS[step.status],
                    active && "ring-2 ring-[var(--accent-green)] ring-offset-2"
                  )}
                >
                  {step.status === "complete" ? <Check size={14} aria-label="Complete" /> : index + 1}
                </span>
                <span>
                  <span className={cn("block whitespace-nowrap text-xs font-semibold", active ? "text-[var(--accent-green-dark)]" : "text-[var(--text-default)]")}>
                    {step.label}
                  </span>
                  <span className="block whitespace-nowrap text-2xs text-[var(--text-muted)]">{step.helper}</span>
                </span>
              </button>
              {index < steps.length - 1 ? (
                <span
                  aria-hidden
                  className={cn(
                    "mx-1 mt-5 h-0.5 min-w-3 flex-1 rounded-full",
                    step.status === "complete" ? "bg-[var(--accent-green)]" : "bg-[var(--surface-border-strong)]"
                  )}
                />
              ) : null}
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
}: {
  position: number;
  total: number;
  onBack: () => void;
  backLabel: string;
  onNext: () => void;
  nextLabel: string;
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
      <Button type="button" className="flex items-center gap-2 whitespace-nowrap text-sm" onClick={onNext}>
        {nextLabel}
        <ArrowRight size={16} aria-hidden />
      </Button>
    </Card>
  );
}
