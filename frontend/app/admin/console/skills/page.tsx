"use client";

import { Plus } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { ReleaseApprovalPanel, SkillDefinitionPanel, SkillRegistryList, TestResultsPanel } from "@/components/admin-console";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Input } from "@/components/ui/Input";
import { Textarea } from "@/components/ui/Textarea";
import { ReasonAction } from "@/components/workbench/AdminControls";
import { ErrorNote, PageFrame, PageSkeleton } from "@/components/workbench/PageFrame";
import { useAdminAction, useAdminSkillsQuery } from "@/hooks/useAdminConsole";
import type { SkillDefinitionDetail } from "@/types/api";

/** Edit the candidate definition. Published versions are never changed. */
function CandidateEditor({ definition, onClose }: { definition: SkillDefinitionDetail; onClose: () => void }) {
  const save = useAdminAction();
  const [contract, setContract] = useState(definition.instructionContract.join("\n"));
  const [scope, setScope] = useState(definition.retrievalScope);
  const [threshold, setThreshold] = useState(definition.evidenceThreshold);
  const [changelog, setChangelog] = useState(definition.changelog);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    await save.mutateAsync({
      path: `/skills/${definition.id}/candidate`,
      method: "PUT",
      body: {
        instructionContract: contract.split("\n").map((line) => line.trim()).filter(Boolean),
        retrievalScope: scope,
        evidenceThreshold: threshold,
        changelog,
      },
    });
    onClose();
  }

  const label = "grid gap-1.5 text-2xs font-semibold uppercase tracking-wide text-[var(--text-muted)]";
  return (
    <Card>
      <form onSubmit={(e) => void onSubmit(e)} className="space-y-3">
        <h2 className="text-base font-semibold text-[var(--text-default)]">
          Edit candidate · {definition.code} {definition.versionLabel}
        </h2>
        <label className={label}>
          Instruction contract (one rule per line)
          <Textarea rows={6} required value={contract} onChange={(e) => setContract(e.target.value)} />
        </label>
        <label className={label}>
          Retrieval scope
          <Input required minLength={3} value={scope} onChange={(e) => setScope(e.target.value)} />
        </label>
        <label className={label}>
          Evidence threshold
          <Input required value={threshold} onChange={(e) => setThreshold(e.target.value)} />
        </label>
        <label className={label}>
          Changelog (recorded in the audit trail)
          <Input required minLength={5} value={changelog} onChange={(e) => setChangelog(e.target.value)} />
        </label>
        <ErrorNote error={save.error} />
        <div className="flex gap-2">
          <Button type="submit" disabled={save.isPending}>
            {save.isPending ? "Saving…" : "Save candidate"}
          </Button>
          <Button type="button" variant="secondary" onClick={onClose}>
            Cancel
          </Button>
        </div>
      </form>
    </Card>
  );
}

export default function AdminConsoleSkillsPage() {
  const skills = useAdminSkillsQuery();
  const [query, setQuery] = useState("");
  const [activeId, setActiveId] = useState<string | null>(null);
  const [editing, setEditing] = useState(false);

  if (skills.isPending) return <PageSkeleton />;
  const data = skills.data;
  if (!data) {
    return (
      <PageFrame breadcrumb="Admin console / Skills" title="Versioned skill definitions">
        <ErrorNote error={skills.error} />
      </PageFrame>
    );
  }

  const needle = query.trim().toLowerCase();
  const registry = data.registry.filter((item) => !needle || item.name.toLowerCase().includes(needle));
  const definition = data.definition;
  const selectedId = activeId ?? definition.id;
  const selected = data.registry.find((item) => item.id === selectedId);

  return (
    <PageFrame
      breadcrumb="Admin console / Skills"
      title="Versioned skill definitions"
      subtitle="Configure instructions and evidence contracts, test behavior, and require independent approval before publishing."
      actions={
        <>
          <Link href="/admin/console/skills/new" className="!no-underline">
            <Button variant="secondary" type="button" className="flex items-center gap-2 whitespace-nowrap">
              <Plus size={16} aria-hidden />
              New skill
            </Button>
          </Link>
          <Button type="button" disabled={selectedId !== definition.id} onClick={() => setEditing(true)}>
            Edit candidate
          </Button>
        </>
      }
    >
      <div className="flex flex-wrap items-center gap-3">
        <Input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search skills" className="min-w-[260px] flex-1" />
        <span className="ml-auto text-xs text-[var(--text-muted)]">
          {data.publishedCount} published · {data.candidateCount} candidates
        </span>
      </div>

      {editing ? <CandidateEditor definition={definition} onClose={() => setEditing(false)} /> : null}

      <div className="grid gap-4 lg:grid-cols-[260px_1fr_320px]">
        <SkillRegistryList items={registry} activeId={selectedId} onSelect={setActiveId} />
        {selectedId === definition.id ? (
          <SkillDefinitionPanel skill={definition} />
        ) : (
          <Card className="h-fit space-y-2">
            <h2 className="text-base font-semibold text-[var(--text-default)]">{selected?.name}</h2>
            <p className="text-sm text-[var(--text-muted)]">{selected?.publishedMeta}</p>
            <p className="text-sm text-[var(--text-muted)]">{selected?.candidateMeta}</p>
            <p className="text-sm text-[var(--text-default)]">
              This skill has no open candidate. Its published definition is immutable.
            </p>
          </Card>
        )}
        <div className="space-y-4">
          <TestResultsPanel
            results={data.testResults}
            actions={
              <p className="text-xs text-[var(--text-muted)]">
                These are the last stored results. No sandbox test runner is connected to this workspace.
              </p>
            }
          />
          <ReleaseApprovalPanel
            approval={data.releaseApproval}
            actions={
              <ReasonAction
                primary
                label={`Approve & publish ${definition.versionLabel}`}
                build={(reason) => ({ path: `/skills/${definition.id}/publish`, body: { reason } })}
              />
            }
          />
        </div>
      </div>
    </PageFrame>
  );
}
