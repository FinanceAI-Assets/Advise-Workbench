import { Button } from "@/components/ui/Button";
import { Check, RefreshCw } from "lucide-react";

import { Card } from "@/components/ui/Card";
import { cn } from "@/lib/utils";
import type { EngagementStep } from "@/types/api";

const CIRCLE_CLASS: Record<EngagementStep["status"], string> = {
  complete: "border-[var(--accent-green)] bg-[#EFF6E6] text-[var(--accent-green-dark)]",
  "in-progress": "border-[var(--accent-green)] text-[var(--accent-green-dark)]",
  upcoming: "border-[var(--surface-border)] text-[var(--text-muted)]",
};

export function EngagementStepper({
  steps,
  onSelect,
  activeId,
}: {
  steps: EngagementStep[];
  onSelect?: (stepId: string) => void;
  /** The step whose view is open; highlighted when the stepper is used as navigation. */
  activeId?: string;
}) {
  return (
    <Card className="flex flex-wrap items-center gap-4 p-4">
      {steps.map((step, i) => (
        <div key={step.id} className="flex items-center gap-4">
          <Button
            type="button"
            variant="ghost"
            disabled={!onSelect}
            onClick={() => onSelect?.(step.id)}
            aria-current={step.id === activeId ? "step" : undefined}
            className={cn(
              "flex items-center gap-2 p-1 text-left font-normal disabled:cursor-default disabled:opacity-100",
              step.id === activeId && "bg-[var(--surface-muted)] ring-1 ring-[var(--accent-green)]"
            )}
          >
            <span
              className={cn(
                "flex h-7 w-7 shrink-0 items-center justify-center rounded-full border text-xs font-semibold",
                CIRCLE_CLASS[step.status]
              )}
            >
              {step.status === "complete" ? (
                <Check size={14} />
              ) : step.icon === "cycle" ? (
                <RefreshCw size={13} />
              ) : (
                step.index
              )}
            </span>
            <div>
              <p className="text-sm font-semibold text-[var(--text-default)]">{step.label}</p>
              <p className="text-xs text-[var(--text-muted)]">{step.helper}</p>
            </div>
          </Button>
          {i < steps.length - 1 ? <span className="text-[var(--text-muted)]">›</span> : null}
        </div>
      ))}
    </Card>
  );
}
