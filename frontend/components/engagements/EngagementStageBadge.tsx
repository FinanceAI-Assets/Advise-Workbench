import { Badge } from "@/components/ui/Badge";
import type { EngagementStage } from "@/types/api";

// Stage colors beyond Badge's existing semantic variants (drafting/sources/brief
// aren't success/warning/error) — composed via className override rather than
// extending the shared Badge variant table for one page's vocabulary.
// Hex values sampled directly from the Figma screenshot for pixel-exact match.
const STAGE_CLASS: Record<EngagementStage, string> = {
  Brief: "border-[var(--surface-border)] bg-[#F4F5F3] text-[#677067]",
  Sources: "border-[var(--surface-border)] bg-[#F4F5F3] text-[#677067]",
  Drafting: "border-[var(--surface-border)] bg-[#EDF2F6] text-[#3B596F]",
  "In review": "border-[var(--surface-border)] bg-[#FCF3E2] text-[#8C5B12]",
  Approved: "border-[var(--surface-border)] bg-[#EFF6E6] text-[#356B12]",
};

export function EngagementStageBadge({ stage }: { stage: EngagementStage }) {
  return <Badge className={STAGE_CLASS[stage]}>{stage}</Badge>;
}
