import { Card } from "@/components/ui/Card";
import { cn } from "@/lib/utils";
import type { EngagementStat } from "@/types/api";

// Helper text tones sampled from the Figma screenshot (kept local to this
// component rather than touching the shared --warning/--success tokens,
// which also drive unrelated run-status pills elsewhere in the app).
const HELPER_TONE_CLASS: Record<NonNullable<EngagementStat["helperTone"]>, string> = {
  default: "text-[var(--text-muted)]",
  warning: "text-[#8C5B12]",
  success: "text-[#356B12]",
};

export function EngagementStatCard({ label, value, helper, helperTone = "default" }: EngagementStat) {
  return (
    <Card className="space-y-2">
      <p className="text-sm text-[var(--text-muted)]">{label}</p>
      <p className="text-3xl font-semibold text-[var(--text-default)]">{value}</p>
      <p className={cn("text-xs", HELPER_TONE_CLASS[helperTone])}>{helper}</p>
    </Card>
  );
}
