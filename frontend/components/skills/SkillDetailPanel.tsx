"use client";

import { ChevronDown, Play, ShieldCheck } from "lucide-react";
import { useState } from "react";

import { EngagementTabs } from "@/components/engagements";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { NoticeCard } from "@/components/ui/NoticeCard";
import type { SkillDetail } from "@/types/api";

type SkillTabKey = "instructions" | "inputs-outputs" | "evidence-policy";

function MetaField({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-2xs font-semibold uppercase tracking-wide text-[var(--text-muted)]">{label}</p>
      <p className="text-sm font-medium text-[var(--text-default)]">{value}</p>
    </div>
  );
}

export function SkillDetailPanel({ skill }: { skill: SkillDetail }) {
  const [tab, setTab] = useState<SkillTabKey>("instructions");

  return (
    <Card className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-base font-semibold text-[var(--text-default)]">{skill.name}</h2>
        <span className="text-xs text-[var(--text-muted)]">
          {skill.code} · {skill.versionLabel}
        </span>
      </div>

      <div className="flex flex-wrap gap-2">
        <Badge className="border-[var(--surface-border)] bg-[#EFF6E6] text-[#356B12]">Published</Badge>
        <Badge className="border-[var(--surface-border)] bg-[var(--surface-muted)] text-[var(--text-muted)]">
          {skill.category}
        </Badge>
        {skill.evidenceRequired ? (
          <Badge className="border-[var(--surface-border)] bg-[var(--surface-muted)] text-[var(--text-muted)]">
            Evidence required
          </Badge>
        ) : null}
      </div>

      <p className="text-sm text-[var(--text-muted)]">{skill.description}</p>

      <EngagementTabs
        tabs={[
          { key: "instructions" as const, label: "Instructions" },
          { key: "inputs-outputs" as const, label: "Inputs & outputs" },
          { key: "evidence-policy" as const, label: "Evidence policy" },
        ]}
        active={tab}
        onChange={setTab}
      />

      {tab === "instructions" ? (
        <div className="space-y-4">
          <div>
            <p className="text-sm font-semibold text-[var(--text-default)]">How this skill works</p>
            <ol className="mt-1 list-inside list-decimal space-y-1 text-sm text-[var(--text-muted)]">
              {skill.howItWorks.map((step) => (
                <li key={step}>{step}</li>
              ))}
            </ol>
          </div>

          <div className="grid gap-4 border-t border-[var(--surface-border)] pt-4 sm:grid-cols-2">
            <MetaField label="Required inputs" value={skill.requiredInputs} />
            <MetaField label="Expected outputs" value={skill.expectedOutputs} />
          </div>

          <NoticeCard
            icon={<ShieldCheck size={18} aria-hidden />}
            title="Evidence policy"
            description={skill.evidencePolicy}
          />

          <div className="grid gap-4 sm:grid-cols-2">
            <MetaField label="Maintained by" value={skill.maintainedBy} />
            <MetaField label="Last published" value={skill.lastPublished} />
          </div>

          <div className="space-y-2 rounded-md bg-[var(--surface-muted)] p-3">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-2xs font-semibold uppercase tracking-wide text-[var(--text-muted)]">Run in engagement</p>
                <p className="text-sm font-medium text-[var(--text-default)]">{skill.runInEngagement}</p>
              </div>
              <ChevronDown size={16} className="text-[var(--text-muted)]" aria-hidden />
            </div>
          </div>

          <Button type="button" className="flex items-center gap-2">
            <Play size={16} aria-hidden />
            Run in engagement
          </Button>
        </div>
      ) : (
        <p className="text-sm text-[var(--text-muted)]">This tab isn&apos;t wired up yet in this preview.</p>
      )}
    </Card>
  );
}
