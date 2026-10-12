import { AlertCircle, UserPlus } from "lucide-react";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { NoticeCard } from "@/components/ui/NoticeCard";
import type { SelectedReviewGovernanceDetail } from "@/types/api";

export function SelectedReviewPanel({ review }: { review: SelectedReviewGovernanceDetail }) {
  return (
    <Card className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-base font-semibold text-[var(--text-default)]">Selected review: {review.code}</h2>
        <span className="text-xs text-[var(--text-muted)]">{review.riskLevel}</span>
      </div>

      <div className="flex flex-wrap gap-2">
        {review.badges.map((badge) => (
          <Badge key={badge} className="border-[var(--surface-border)] bg-[#FCF3E2] text-[#8C5B12]">
            {badge}
          </Badge>
        ))}
      </div>

      <h3 className="text-lg font-semibold text-[var(--text-default)]">{review.title}</h3>

      <div className="grid gap-4 sm:grid-cols-2">
        <div>
          <p className="text-2xs font-semibold uppercase tracking-wide text-[var(--text-muted)]">Artifact / owner</p>
          <p className="text-sm font-medium text-[var(--text-default)]">{review.artifactOwner}</p>
        </div>
        <div>
          <p className="text-2xs font-semibold uppercase tracking-wide text-[var(--text-muted)]">Assigned approver</p>
          <p className="text-sm font-medium text-[var(--text-default)]">{review.assignedApprover}</p>
        </div>
      </div>

      <p className="text-sm text-[var(--text-muted)]">{review.riskDescription}</p>

      {review.warning ? (
        <NoticeCard tone="warning" icon={<AlertCircle size={18} aria-hidden />} title={review.warning.title} description={review.warning.description} />
      ) : null}

      <div className="flex flex-wrap gap-2">
        <Button type="button" className="flex items-center gap-2 whitespace-nowrap text-sm">
          <UserPlus size={16} aria-hidden />
          Assign reviewer
        </Button>
        <Button variant="secondary" type="button" disabled className="whitespace-nowrap text-sm">
          Approve export
        </Button>
      </div>

      <p className="text-xs text-[var(--text-muted)]">{review.footnote}</p>
    </Card>
  );
}
