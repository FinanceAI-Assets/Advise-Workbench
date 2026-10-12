import { Card } from "@/components/ui/Card";
import { cn } from "@/lib/utils";
import type { AdminStat } from "@/types/api";

const HELPER_TONE_CLASS: Record<NonNullable<AdminStat["helperTone"]>, string> = {
  default: "text-[var(--text-muted)]",
  warning: "text-[#8C5B12]",
  success: "text-[#356B12]",
};

export function AdminStatCard({ label, value, helper, helperTone = "default" }: AdminStat) {
  return (
    <Card className="space-y-2">
      <p className="text-sm text-[var(--text-muted)]">{label}</p>
      <p className="text-3xl font-semibold text-[var(--text-default)]">{value}</p>
      <p className={cn("text-xs", HELPER_TONE_CLASS[helperTone])}>{helper}</p>
    </Card>
  );
}
