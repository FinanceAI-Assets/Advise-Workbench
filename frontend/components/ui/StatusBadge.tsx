import { cn } from "@/lib/utils";

export type StatusTone = "success" | "warning" | "error" | "info" | "neutral";

const TONE_CLASS: Record<StatusTone, string> = {
  success: "border-[#D3E6BF] bg-[#EFF6E6] text-[#356B12]",
  warning: "border-[#F1DDB4] bg-[#FCF3E2] text-[#8C5B12]",
  error: "border-[#EFC9C3] bg-[#FBEFEB] text-[#A53E37]",
  info: "border-[#D3DEE7] bg-[#EDF2F6] text-[#3B596F]",
  neutral: "border-[var(--surface-border)] bg-[var(--surface-muted)] text-[var(--text-muted)]",
};

/** The status pill of a table row: a coloured dot and label, green / amber / red / blue / grey. */
export function StatusBadge({ tone, children, className }: { tone?: StatusTone; children: string; className?: string }) {
  tone ??= statusTone(children);
  return (
    <span
      className={cn(
        "inline-flex shrink-0 items-center gap-1.5 whitespace-nowrap rounded border px-2 py-0.5 text-2xs font-medium leading-4",
        TONE_CLASS[tone],
        className
      )}
    >
      <span className="h-1.5 w-1.5 rounded-full bg-current" aria-hidden />
      {children}
    </span>
  );
}

// Checked in order, so "Not approved" is amber before "approved" makes it green.
const TONE_RULES: Array<[RegExp, StatusTone]> = [
  [/fail|error|reject|block|high|risk|overdue|breach|not readable|ocr failed/i, "error"],
  [/not |pending|review|request|progress|processing|queued|draft|medium|due|lock|wait|open|candidate|gap|attention|approval$/i, "warning"],
  [/approved|published|complete|passed|pass$|permitted|active|resolved|done|indexed|accepted|live|ready|healthy|ok$/i, "success"],
];

/** The tone of a status label: red for failures and high risk, amber for anything waiting, green for done. */
export function statusTone(label: string, overrides?: Record<string, StatusTone>): StatusTone {
  if (overrides?.[label]) return overrides[label];
  return TONE_RULES.find(([pattern]) => pattern.test(label))?.[1] ?? "neutral";
}
