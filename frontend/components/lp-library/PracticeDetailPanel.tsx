"use client";

import { Plus } from "lucide-react";
import { useState } from "react";

import { EngagementTabs } from "@/components/engagements";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import type { PracticeDetail } from "@/types/api";

type PracticeTabKey = "overview" | "evidence" | "versions";

function MetaField({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-2xs font-semibold uppercase tracking-wide text-[var(--text-muted)]">{label}</p>
      <p className="text-sm font-medium text-[var(--text-default)]">{value}</p>
    </div>
  );
}

export function PracticeDetailPanel({ practice }: { practice: PracticeDetail }) {
  const [tab, setTab] = useState<PracticeTabKey>("overview");

  return (
    <Card className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-base font-semibold text-[var(--text-default)]">Practice detail</h2>
        <span className="text-xs text-[var(--text-muted)]">{practice.code}</span>
      </div>

      <div className="flex flex-wrap gap-2">
        <Badge className="border-[var(--surface-border)] bg-[#EFF6E6] text-[#356B12]">{practice.status}</Badge>
        <Badge className="border-[var(--surface-border)] bg-[var(--surface-muted)] text-[var(--text-muted)]">
          {practice.versionLabel}
        </Badge>
        <Badge className="border-[var(--surface-border)] bg-[var(--surface-muted)] text-[var(--text-muted)]">
          {practice.maturity}
        </Badge>
      </div>

      <div>
        <h3 className="text-xl font-semibold text-[var(--text-default)]">{practice.title}</h3>
        <p className="mt-1 text-sm text-[var(--text-muted)]">{practice.description}</p>
      </div>

      <EngagementTabs
        tabs={[
          { key: "overview" as const, label: "Overview" },
          { key: "evidence" as const, label: "Evidence" },
          { key: "versions" as const, label: "Versions" },
        ]}
        active={tab}
        onChange={setTab}
      />

      {tab === "overview" ? (
        <div className="space-y-4">
          <div>
            <p className="text-sm font-semibold text-[var(--text-default)]">Recommended when</p>
            <p className="text-sm text-[var(--text-muted)]">{practice.recommendedWhen}</p>
          </div>
          <div>
            <p className="text-sm font-semibold text-[var(--text-default)]">Core guidance</p>
            <ul className="mt-1 list-inside list-disc space-y-1 text-sm text-[var(--text-muted)]">
              {practice.coreGuidance.map((line) => (
                <li key={line}>{line}</li>
              ))}
            </ul>
          </div>
          <div className="grid gap-4 border-t border-[var(--surface-border)] pt-4 sm:grid-cols-2">
            <MetaField label="Source attribution" value={practice.sourceAttribution} />
            <MetaField label="Practice owner" value={practice.practiceOwner} />
            <MetaField label="Approved" value={practice.approvedMeta} />
            <MetaField label="Source quality" value={practice.sourceQuality} />
          </div>
          <Button type="button" className="flex items-center gap-2">
            <Plus size={16} aria-hidden />
            Add to Northstar conversation
          </Button>
        </div>
      ) : (
        <p className="text-sm text-[var(--text-muted)]">This tab isn&apos;t wired up yet in this preview.</p>
      )}
    </Card>
  );
}
