"use client";

import { useState } from "react";

import { EngagementTabs } from "@/components/engagements";
import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import type { SkillDefinitionDetail } from "@/types/api";

type SkillDefinitionTabKey = "definition" | "inputs-outputs" | "permissions" | "history";

function MetaField({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-2xs font-semibold uppercase tracking-wide text-[var(--text-muted)]">{label}</p>
      <p className="text-sm font-medium text-[var(--text-default)]">{value}</p>
    </div>
  );
}

export function SkillDefinitionPanel({ skill }: { skill: SkillDefinitionDetail }) {
  const [tab, setTab] = useState<SkillDefinitionTabKey>("definition");

  return (
    <Card className="space-y-4">
      <div className="flex items-start justify-between">
        <h2 className="text-base font-semibold text-[var(--text-default)]">{skill.name}</h2>
        <div className="text-right text-xs text-[var(--text-muted)]">
          <p>
            {skill.code} · {skill.versionLabel}
          </p>
          <p>Owner: {skill.owner}</p>
        </div>
      </div>

      <Badge className="border-[var(--surface-border)] bg-[#FCF3E2] text-[#8C5B12]">{skill.approvalState}</Badge>

      <EngagementTabs
        tabs={[
          { key: "definition" as const, label: "Definition" },
          { key: "inputs-outputs" as const, label: "Inputs & outputs" },
          { key: "permissions" as const, label: "Permissions" },
          { key: "history" as const, label: "History" },
        ]}
        active={tab}
        onChange={setTab}
      />

      {tab === "definition" ? (
        <div className="space-y-4">
          <div>
            <p className="text-sm font-semibold text-[var(--text-default)]">Instruction contract</p>
            <pre className="mt-2 whitespace-pre-wrap rounded-md bg-[var(--surface-muted)] p-3 font-mono text-xs text-[var(--text-default)]">
              {skill.instructionContract.join("\n")}
            </pre>
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            <MetaField label="Required input schema" value={skill.requiredInputSchema} />
            <MetaField label="Output schema" value={skill.outputSchema} />
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <MetaField label="Retrieval scope" value={skill.retrievalScope} />
            <MetaField label="Evidence threshold" value={skill.evidenceThreshold} />
          </div>

          <div>
            <p className="text-sm font-semibold text-[var(--text-default)]">Permissions &amp; publishing separation</p>
            <table className="mt-2 w-full text-left text-sm">
              <thead>
                <tr className="border-y border-[var(--surface-border)] bg-[var(--surface-muted)] text-xs text-[var(--text-muted)]">
                  <th className="px-3 py-2 font-medium">Role</th>
                  <th className="px-3 py-2 font-medium">Use skill</th>
                  <th className="px-3 py-2 font-medium">Define / approve</th>
                </tr>
              </thead>
              <tbody>
                {skill.permissions.map((perm) => (
                  <tr key={perm.id} className="border-b border-[var(--surface-border)] last:border-b-0">
                    <td className="px-3 py-2 font-medium text-[var(--text-default)]">{perm.role}</td>
                    <td className="px-3 py-2 text-[var(--text-muted)]">{perm.useSkill}</td>
                    <td className="px-3 py-2 text-[var(--text-muted)]">{perm.defineApprove}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <p className="border-t border-[var(--surface-border)] pt-3 text-xs text-[var(--text-muted)]">{skill.changelog}</p>
        </div>
      ) : (
        <p className="text-sm text-[var(--text-muted)]">This tab isn&apos;t wired up yet in this preview.</p>
      )}
    </Card>
  );
}
