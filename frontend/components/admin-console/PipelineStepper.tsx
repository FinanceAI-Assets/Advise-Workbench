import { Circle, CircleCheck, Scan } from "lucide-react";

import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { cn } from "@/lib/utils";
import type { EngagementStep } from "@/types/api";

function StepIcon({ status }: { status: EngagementStep["status"] }) {
  if (status === "complete") return <CircleCheck size={16} className="text-[var(--accent-green-dark)]" aria-hidden />;
  if (status === "in-progress") return <Scan size={16} className="text-[var(--accent-green-dark)]" aria-hidden />;
  return <Circle size={16} className="text-[var(--text-muted)]" aria-hidden />;
}

/** The five library ingestion steps in one row; each step opens its view. */
export function PipelineStepper({
  steps,
  activeId,
  onSelect,
}: {
  steps: EngagementStep[];
  activeId: string;
  onSelect: (stepId: string) => void;
}) {
  return (
    <Card className="p-0">
      <ol className="grid grid-cols-2 gap-1 p-2 sm:grid-cols-3 lg:grid-cols-5">
        {steps.map((step) => (
          <li key={step.id}>
            <Button
              type="button"
              variant="ghost"
              onClick={() => onSelect(step.id)}
              aria-current={step.id === activeId ? "step" : undefined}
              className={cn(
                "flex w-full items-start gap-2.5 px-2 py-2 text-left font-normal hover:bg-[var(--surface-muted)]",
                // The first step's view is the library overview, which the design shows without a highlight.
                step.id === activeId && activeId !== steps[0]?.id && "bg-[var(--surface-muted)]"
              )}
            >
              <span className="mt-px">
                <StepIcon status={step.status} />
              </span>
              <span>
                <span className="block text-xs font-semibold text-[var(--text-default)]">{step.label}</span>
                <span className="block text-2xs text-[var(--text-muted)]">{step.helper}</span>
              </span>
            </Button>
          </li>
        ))}
      </ol>
    </Card>
  );
}
