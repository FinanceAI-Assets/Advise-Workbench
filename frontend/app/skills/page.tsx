"use client";

import { History, Play, Search } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { SkillCardTile, SkillDetailPanel } from "@/components/skills";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { Input } from "@/components/ui/Input";
import { Select } from "@/components/ui/Select";
import { ErrorNote, PageFrame, PageSkeleton } from "@/components/workbench/PageFrame";
import { useEngagementsQuery } from "@/hooks/useEngagements";
import { useSelectSkillMutation, useSkillsQuery } from "@/hooks/useWorkbench";

/** Choose an engagement and make this skill the active skill of its conversation. */
function RunInEngagement({ skillId }: { skillId: string }) {
  const router = useRouter();
  const engagements = useEngagementsQuery({ q: "", status: "active", mine: false, page: 1 });
  const select = useSelectSkillMutation();
  const [projectId, setProjectId] = useState("");
  const rows = engagements.data?.items ?? [];
  const target = projectId || rows[0]?.id || "";

  async function run() {
    const result = await select.mutateAsync({ skillId, projectId: target });
    router.push(result.href);
  }

  return (
    <div className="space-y-3 rounded-md bg-[var(--surface-muted)] p-3">
      <label className="grid gap-1.5 text-2xs font-semibold uppercase tracking-wide text-[var(--text-muted)]">
        Run in engagement
        <Select value={target} onChange={(e) => setProjectId(e.target.value)}>
          {rows.map((row) => (
            <option key={row.id} value={row.id}>
              {row.name} · {row.code}
            </option>
          ))}
        </Select>
      </label>
      <Button className="flex items-center gap-2" disabled={!target || select.isPending} onClick={() => void run()}>
        <Play size={16} aria-hidden />
        {select.isPending ? "Opening…" : "Run in engagement"}
      </Button>
      <p className="text-xs text-[var(--text-muted)]">
        Sets this skill on the engagement&apos;s conversation and opens it. Outputs need independent review before export.
      </p>
      <ErrorNote error={select.error} />
    </div>
  );
}

// Skills catalog: published advisory workflows and how to run one in an engagement.
export default function SkillsPage() {
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState("");
  const skills = useSkillsQuery(query);

  if (skills.isPending && !skills.data) return <PageSkeleton />;
  const cards = skills.data?.cards ?? [];
  const activeId = cards.some((c) => c.id === selected) ? selected : (cards[0]?.id ?? "");
  const detail = skills.data?.skills[activeId];
  const card = cards.find((c) => c.id === activeId);

  return (
    <PageFrame
      breadcrumb="User workspace / Skills"
      title="Expert workflows, repeatable outputs"
      subtitle="Published skills carry an evidence policy. Run one inside an engagement to produce source-linked drafts."
      actions={
        <Link href="/skills/runs" className="!no-underline">
          <Button variant="secondary" className="flex items-center gap-2">
            <History size={16} aria-hidden />
            Skill run history
          </Button>
        </Link>
      }
    >
      <ErrorNote error={skills.error} />
      <div className="flex flex-wrap items-center gap-3">
        <div className="relative min-w-[260px] flex-1">
          <Search size={16} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-[var(--text-muted)]" aria-hidden />
          <Input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search skills" className="pl-9" />
        </div>
        <span className="text-xs text-[var(--text-muted)]">{skills.data?.totalPublished ?? 0} published skills</span>
      </div>

      {cards.length === 0 ? (
        <EmptyState
          title={query ? "No skills match" : "No skills in the catalog"}
          description={query ? "Try a different term." : "Ask an administrator to publish skills."}
        />
      ) : (
        <div className="grid gap-4 lg:grid-cols-[1fr_440px]">
          <div className="grid gap-3 sm:grid-cols-2">
            {cards.map((item) => (
              <SkillCardTile key={item.id} skill={item} active={item.id === activeId} onSelect={() => setSelected(item.id)} />
            ))}
          </div>
          <div>
            {detail ? (
              <SkillDetailPanel skill={detail} actions={<RunInEngagement skillId={activeId} />} />
            ) : card ? (
              <Card className="space-y-3">
                <h2 className="text-base font-semibold text-[var(--text-default)]">{card.name}</h2>
                <p className="text-sm text-[var(--text-muted)]">
                  {card.versionLabel} · {card.formats}
                </p>
                <p className="text-sm text-[var(--text-default)]">{card.description}</p>
                <RunInEngagement skillId={activeId} />
              </Card>
            ) : null}
          </div>
        </div>
      )}
    </PageFrame>
  );
}
