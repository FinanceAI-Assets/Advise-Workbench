"use client";

import { Plus } from "lucide-react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";

import { RerunTestsButton } from "@/components/skill-management/SkillActions";
import {
  BUTTON_COMPACT,
  BUTTON_SECONDARY,
  Fact,
  Note,
  Panel,
  RecordList,
  SKILLS_HOME,
  TabLinks,
} from "@/components/skill-management/SkillParts";
import { Button } from "@/components/ui/Button";
import { PageFrame } from "@/components/workbench/PageFrame";
import { useSkillManagement } from "@/hooks/useSkillManagement";
import { candidateGate, passedCount, type Skill, totalCount } from "@/lib/skillManagement";
import { cn } from "@/lib/utils";

function RegistryFrame({ active, crumb, title, subtitle, children }: { active: "published" | "candidates"; crumb: string; title: string; subtitle: string; children: React.ReactNode }) {
  const { skills } = useSkillManagement();
  const published = skills.filter((s) => s.published).length;
  const candidates = skills.filter((s) => s.candidate).length;
  return (
    <PageFrame
      breadcrumb={`Admin console / Skills management / ${crumb}`}
      title={title}
      subtitle={subtitle}
      actions={
        <Link href={`${SKILLS_HOME}/new`} className="!no-underline">
          <Button type="button" className={`${BUTTON_COMPACT} flex items-center gap-2`}>
            <Plus size={14} aria-hidden />
            New skill
          </Button>
        </Link>
      }
    >
      <TabLinks
        active={active}
        tabs={[
          { key: "published", label: `Published (${published})`, href: SKILLS_HOME },
          { key: "candidates", label: `Candidates (${candidates})`, href: `${SKILLS_HOME}/candidates` },
        ]}
      />
      {children}
    </PageFrame>
  );
}

type PeekTab = "definition" | "io" | "permissions" | "history";
const PEEK_TABS: Array<{ key: PeekTab; label: string }> = [
  { key: "definition", label: "Definition" },
  { key: "io", label: "Inputs & outputs" },
  { key: "permissions", label: "Permissions" },
  { key: "history", label: "History" },
];

/** The selected published skill, summarised in four small tabs. */
function PublishedPeek({ skill }: { skill: Skill }) {
  const [tab, setTab] = useState<PeekTab>("definition");
  const p = skill.published!;
  return (
    <Panel title={`Selected: ${skill.name}`} className="h-fit">
      <div className="flex flex-wrap gap-x-5 border-b border-[var(--surface-border)]" role="tablist" aria-label={`${skill.name} details`}>
        {PEEK_TABS.map((item) => (
          <Button
            key={item.key}
            type="button"
            variant="ghost"
            role="tab"
            aria-selected={tab === item.key}
            onClick={() => setTab(item.key)}
            className={cn(
              "-mb-px rounded-none border-b-2 px-0 pb-2 pt-0 text-xs font-normal hover:bg-transparent",
              tab === item.key
                ? "border-[var(--accent-green)] font-medium text-[var(--accent-green-dark)]"
                : "border-transparent text-[var(--text-muted)] hover:text-[var(--text-default)]"
            )}
          >
            {item.label}
          </Button>
        ))}
      </div>

      {tab === "definition" ? (
        <>
          <p className="text-xs leading-relaxed text-[var(--text-default)]">{p.summary}</p>
          <Fact label="Input">{p.inputSummary}</Fact>
          <Fact label="Output">{p.outputSummary}</Fact>
          <Fact label="Approval">
            {p.approvedBy} · Published {p.version} · {p.publishedOn}
          </Fact>
        </>
      ) : tab === "io" ? (
        <>
          <Fact label="Inputs">{p.inputs.map((f) => `${f.name}: ${f.type}`).join(" · ")}</Fact>
          <Fact label="Outputs">{p.outputs.map((o) => o.name).join(" · ")}</Fact>
        </>
      ) : tab === "permissions" ? (
        <>
          <Fact label="Run access">{p.permittedRoles}</Fact>
          <Fact label="Owner / approver">
            {skill.owner} / {skill.approver}
          </Fact>
        </>
      ) : (
        <ul className="space-y-1.5 text-xs text-[var(--text-default)]">
          {skill.history.slice(0, 3).map((h) => (
            <li key={`${h.title}-${h.at}`}>
              {h.title} <span className="text-[var(--text-muted)]">· {h.actor} · {h.at}</span>
            </li>
          ))}
        </ul>
      )}

      <div className="flex flex-wrap gap-2">
        {skill.candidate ? (
          <Link href={`${SKILLS_HOME}/${skill.id}`} className="!no-underline">
            <Button type="button" variant="secondary" className={BUTTON_SECONDARY}>
              Open candidate {skill.candidate.version}
            </Button>
          </Link>
        ) : (
          <Link href={`${SKILLS_HOME}/new?from=${skill.id}`} className="!no-underline">
            <Button type="button" variant="secondary" className={BUTTON_SECONDARY}>
              Create next candidate
            </Button>
          </Link>
        )}
        <Link href={`${SKILLS_HOME}/${skill.id}`} className="self-center text-xs">
          Full definition
        </Link>
      </div>
    </Panel>
  );
}

/** Published skills, with the one named by ?skill= (or the first) selected. */
export function PublishedRegistry() {
  const { skills } = useSkillManagement();
  const params = useSearchParams();
  const router = useRouter();
  const published = skills.filter((s) => s.published);
  const selected = published.find((s) => s.id === params.get("skill")) ?? published[0];

  return (
    <RegistryFrame
      active="published"
      crumb="Skill registry"
      title="Skill registry"
      subtitle="Published versions and selected skill configuration. Definitions are immutable after publication."
    >
      <div className="grid grid-cols-1 gap-5 lg:grid-cols-[minmax(0,1fr)_380px]">
        <Panel title="Published registry">
          <RecordList
            label="Published skills"
            columns={["Skill", "Version", "Owner", "Output"]}
            rows={published.map((s) => ({
              key: s.id,
              title: s.name,
              meta: [s.published!.version, s.owner, s.published!.formats],
              highlight: s.id === selected?.id,
              onSelect: () => router.replace(`${SKILLS_HOME}?skill=${s.id}`, { scroll: false }),
            }))}
          />
        </Panel>
        {selected ? <PublishedPeek key={selected.id} skill={selected} /> : null}
      </div>
    </RegistryFrame>
  );
}

/** Open candidates: tested separately from the published definitions they will replace. */
export function CandidateRegistry() {
  const { skills } = useSkillManagement();
  const params = useSearchParams();
  const router = useRouter();
  const candidates = skills.filter((s) => s.candidate);
  const selected = candidates.find((s) => s.id === params.get("skill")) ?? candidates[0];
  const c = selected?.candidate;
  const engagement = selected?.pinnedRun.split(" ")[0];

  return (
    <RegistryFrame
      active="candidates"
      crumb="Skill registry / Candidates"
      title="Skill registry candidates"
      subtitle="Candidate changes are tested independently of published definitions."
    >
      <div className="grid grid-cols-1 gap-5 lg:grid-cols-[minmax(0,1fr)_340px]">
        <Panel title="Candidate registry">
          {candidates.length ? (
            <RecordList
              label="Candidates"
              columns={["Skill", "Candidate", "Owner / reviewer", "Gate"]}
              rows={candidates.map((s) => ({
                key: s.id,
                title: s.name,
                meta: [`${s.candidate!.version} · ${s.candidate!.revision}`, `${s.owner} / ${s.approver}`, candidateGate(s)],
                highlight: s.id === selected?.id,
                onSelect: () => router.replace(`${SKILLS_HOME}/candidates?skill=${s.id}`, { scroll: false }),
              }))}
            />
          ) : (
            <p className="text-xs text-[var(--text-muted)]">No open candidates. Create one from a published skill or define a new skill.</p>
          )}
          {selected ? (
            <Note title="Version separation">
              {selected.published
                ? `Published ${selected.name} ${selected.published.version} remains active${engagement ? ` for ${engagement}` : ""}. `
                : `${selected.name} has no published version yet. `}
              A saved candidate cannot be used in engagement runs.
            </Note>
          ) : null}
        </Panel>

        {selected && c ? (
          <Panel title="Selected candidate" className="h-fit">
            <Fact label={selected.name}>
              {c.version} · Revision {c.revision}
            </Fact>
            <Fact label="Change">{c.change}</Fact>
            <Fact label={c.lastTest?.revision === c.revision ? "Latest test" : "Previous test"}>
              {c.lastTest ? `${c.lastTest.id} · ${passedCount(c.lastTest)} / ${totalCount(c.lastTest)} passed` : "Not run yet"}
            </Fact>
            <div className="flex flex-col items-start gap-2">
              <Link href={`${SKILLS_HOME}/${selected.id}`} className="!no-underline">
                <Button type="button" variant="secondary" className={BUTTON_SECONDARY}>
                  Open candidate definition
                </Button>
              </Link>
              {c.status === "In review" ? (
                <Link href={`${SKILLS_HOME}/${selected.id}/release`} className="!no-underline">
                  <Button type="button" className={BUTTON_COMPACT}>
                    Open release review
                  </Button>
                </Link>
              ) : (
                <RerunTestsButton skillId={selected.id} />
              )}
            </div>
          </Panel>
        ) : null}
      </div>
    </RegistryFrame>
  );
}
