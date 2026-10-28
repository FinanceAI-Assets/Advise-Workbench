import { TriangleAlert } from "lucide-react";

import { cn } from "@/lib/utils";

export type LibraryBadgeTone = "success" | "warning" | "error" | "neutral";

const TONE_CLASS: Record<LibraryBadgeTone, string> = {
  success: "border-[#D3E6BF] bg-[#EFF6E6] text-[#356B12]",
  warning: "border-[#F1DDB4] bg-[#FCF3E2] text-[#8C5B12]",
  error: "border-[#EFC9C3] bg-[#FBEFEB] text-[#A53E37]",
  neutral: "border-[var(--surface-border)] bg-[var(--surface-muted)] text-[var(--text-muted)]",
};

// Library states shown in the inventory, the ingestion job and the review panel.
const STATE_TONE: Record<string, LibraryBadgeTone> = {
  Indexed: "success",
  Published: "success",
  Passed: "success",
  "Quality review": "warning",
  "In review": "warning",
  "Approval blocked": "warning",
  Pending: "neutral",
  "Not eligible": "neutral",
  "OCR failed": "error",
  "Not readable": "error",
};

export function libraryTone(state: string): LibraryBadgeTone {
  return STATE_TONE[state] ?? "neutral";
}

/** Compact status pill used across the library management screen. */
export function LibraryBadge({
  children,
  tone,
  className,
}: {
  children: string;
  tone?: LibraryBadgeTone;
  className?: string;
}) {
  return (
    <span
      className={cn(
        "inline-flex shrink-0 items-center whitespace-nowrap rounded border px-2 py-0.5 text-2xs font-medium leading-4",
        TONE_CLASS[tone ?? libraryTone(children)],
        className
      )}
    >
      {children}
    </span>
  );
}

/** Amber notice for a blocker or connector exception inside a library panel. */
export function LibraryWarning({ title, description }: { title: string; description: string }) {
  return (
    <div className="flex items-start gap-2.5 rounded-md border border-[#F1DDB4] bg-[#FCF3E2] px-3 py-2.5 text-[#8C5B12]">
      <TriangleAlert size={14} className="mt-0.5 shrink-0" aria-hidden />
      <div>
        <p className="text-xs font-semibold">{title}</p>
        <p className="text-2xs">{description}</p>
      </div>
    </div>
  );
}
