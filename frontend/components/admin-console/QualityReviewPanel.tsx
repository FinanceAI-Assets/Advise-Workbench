"use client";

import { AlertCircle } from "lucide-react";
import { useState } from "react";

import { EngagementTabs } from "@/components/engagements";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { NoticeCard } from "@/components/ui/NoticeCard";
import type { QualityReviewDetail } from "@/types/api";

type QualityReviewTabKey = "metadata" | "source-quality" | "versions";

function MetaField({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-2xs font-semibold uppercase tracking-wide text-[var(--text-muted)]">{label}</p>
      <p className="text-sm font-medium text-[var(--text-default)]">{value}</p>
    </div>
  );
}

export function QualityReviewPanel({ review }: { review: QualityReviewDetail }) {
  const [tab, setTab] = useState<QualityReviewTabKey>("metadata");

  return (
    <Card className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-base font-semibold text-[var(--text-default)]">Quality review &amp; metadata</h2>
        <span className="text-xs text-[var(--text-muted)]">{review.code}</span>
      </div>

      <h3 className="text-lg font-semibold text-[var(--text-default)]">{review.title}</h3>

      <div className="flex flex-wrap gap-2">
        <Badge className="border-[var(--surface-border)] bg-[var(--surface-muted)] text-[var(--text-muted)]">
          {review.versionLabel}
        </Badge>
        <Badge className="border-[var(--surface-border)] bg-[#FCF3E2] text-[#8C5B12]">{review.approvalState}</Badge>
      </div>

      <EngagementTabs
        tabs={[
          { key: "metadata" as const, label: "Metadata" },
          { key: "source-quality" as const, label: "Source quality" },
          { key: "versions" as const, label: "Versions" },
        ]}
        active={tab}
        onChange={setTab}
      />

      {tab === "metadata" ? (
        <div className="space-y-4">
          <div className="grid gap-4 sm:grid-cols-2">
            <MetaField label="Taxonomy" value={review.taxonomy} />
            <MetaField label="Maturity" value={review.maturity} />
            <MetaField label="Practice owner" value={review.practiceOwner} />
            <MetaField label="Approver" value={review.approver} />
          </div>

          <div>
            <p className="text-sm font-semibold text-[var(--text-default)]">Source quality checks</p>
            <ul className="mt-2 space-y-2">
              {review.sourceQualityChecks.map((check) => (
                <li key={check.id} className="flex items-center justify-between text-sm">
                  <span className="text-[var(--text-default)]">{check.label}</span>
                  <Badge
                    className={
                      check.state === "Passed"
                        ? "border-[var(--surface-border)] bg-[#EFF6E6] text-[#356B12]"
                        : "border-[var(--surface-border)] bg-[#FCF3E2] text-[#8C5B12]"
                    }
                  >
                    {check.state}
                  </Badge>
                </li>
              ))}
            </ul>
          </div>

          {review.warning ? (
            <NoticeCard tone="warning" icon={<AlertCircle size={18} aria-hidden />} title={review.warning.title} description={review.warning.description} />
          ) : null}

          <p className="text-xs text-[var(--text-muted)]">{review.footnote}</p>

          <div className="flex flex-wrap gap-2">
            <Button variant="secondary" type="button" className="whitespace-nowrap text-sm">
              Request correction
            </Button>
            <Button type="button" disabled className="whitespace-nowrap text-sm">
              Approve &amp; publish
            </Button>
          </div>
        </div>
      ) : (
        <p className="text-sm text-[var(--text-muted)]">This tab isn&apos;t wired up yet in this preview.</p>
      )}
    </Card>
  );
}
