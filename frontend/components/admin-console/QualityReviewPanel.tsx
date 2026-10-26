"use client";

import type { ReactNode } from "react";
import { useState } from "react";

import { LibraryBadge, LibraryWarning } from "@/components/admin-console/LibraryStatus";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { cn } from "@/lib/utils";
import type { QualityReviewDetail } from "@/types/api";

type QualityReviewTabKey = "metadata" | "source-quality" | "versions";

const TABS: Array<{ key: QualityReviewTabKey; label: string }> = [
  { key: "metadata", label: "Metadata" },
  { key: "source-quality", label: "Source quality" },
  { key: "versions", label: "Versions" },
];

function MetaField({ label, value, className }: { label: string; value: string; className?: string }) {
  return (
    <div className={className}>
      <p className="text-2xs font-medium uppercase tracking-wide text-[var(--text-muted)]">{label}</p>
      <p className="mt-0.5 text-xs font-semibold text-[var(--text-default)]">{value}</p>
    </div>
  );
}

export function QualityReviewPanel({ review, actions }: { review: QualityReviewDetail; actions?: ReactNode }) {
  const [tab, setTab] = useState<QualityReviewTabKey>("metadata");

  return (
    <Card className="space-y-4">
      <div className="flex items-center justify-between gap-3">
        <h2 className="text-sm font-semibold text-[var(--text-default)]">Quality review &amp; metadata</h2>
        <span className="text-2xs text-[var(--text-muted)]">{review.code}</span>
      </div>

      <div className="space-y-2">
        <h3 className="text-lg font-semibold leading-tight text-[var(--text-default)]">{review.title}</h3>
        <div className="flex flex-wrap gap-2">
          <LibraryBadge tone="neutral">{review.versionLabel}</LibraryBadge>
          <LibraryBadge tone={review.approvalState === "Published" ? "success" : "warning"}>{review.approvalState}</LibraryBadge>
        </div>
      </div>

      <div className="flex gap-5 border-b border-[var(--surface-border)]" role="tablist" aria-label="Review details">
        {TABS.map((item) => (
          <Button
            key={item.key}
            type="button"
            variant="ghost"
            role="tab"
            aria-selected={tab === item.key}
            onClick={() => setTab(item.key)}
            className={cn(
              "-mb-px rounded-none border-b-2 px-0 pb-2 pt-0 text-xs font-medium hover:bg-transparent",
              tab === item.key
                ? "border-[var(--accent-green)] text-[var(--text-default)]"
                : "border-transparent text-[var(--text-muted)] hover:text-[var(--text-default)]"
            )}
          >
            {item.label}
          </Button>
        ))}
      </div>

      {tab === "metadata" ? (
        <div className="space-y-4">
          <div className="grid gap-x-4 gap-y-3 sm:grid-cols-2">
            <MetaField label="Taxonomy" value={review.taxonomy} />
            <MetaField label="Maturity" value={review.maturity} />
            <MetaField label="Practice owner" value={review.practiceOwner} />
            <MetaField label="Approver" value={review.approver} />
            {review.sourceAttribution ? (
              <MetaField label="Source attribution & rights" value={review.sourceAttribution} className="sm:col-span-2" />
            ) : null}
          </div>

          <div className="border-t border-[var(--surface-border)] pt-4">
            <p className="text-xs font-semibold text-[var(--text-default)]">Source quality checks</p>
            <ul className="mt-1 divide-y divide-[var(--surface-border)]">
              {review.sourceQualityChecks.map((check) => (
                <li key={check.id} className="flex items-center justify-between gap-3 py-2.5 text-2xs text-[var(--text-default)]">
                  <span>{check.label}</span>
                  <LibraryBadge tone={check.state === "Passed" ? "success" : "warning"}>{check.state}</LibraryBadge>
                </li>
              ))}
            </ul>
          </div>

          {review.warning ? <LibraryWarning {...review.warning} /> : null}

          <p className="text-2xs text-[var(--text-muted)]">{review.footnote}</p>

          {actions}
        </div>
      ) : (
        <p className="text-xs text-[var(--text-muted)]">This tab isn&apos;t wired up yet in this preview.</p>
      )}
    </Card>
  );
}
