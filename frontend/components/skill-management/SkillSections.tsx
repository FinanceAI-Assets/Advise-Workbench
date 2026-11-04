"use client";

import Link from "next/link";

import { RerunTestsButton } from "@/components/skill-management/SkillActions";
import {
  BUTTON_COMPACT,
  BUTTON_SECONDARY,
  Fact,
  FieldBox,
  Note,
  Panel,
  RecordList,
  SKILLS_HOME,
} from "@/components/skill-management/SkillParts";
import { Button } from "@/components/ui/Button";
import { allPassed, reviewBlocker, type Skill, type SkillDefinition } from "@/lib/skillManagement";

/** The definition the tabs describe: the open candidate, otherwise the published version. */
const current = (skill: Skill): SkillDefinition => (skill.candidate ?? skill.published) as SkillDefinition;

function Contract({ paragraphs }: { paragraphs: string[] }) {
  return (
    <div className="space-y-3 text-xs leading-relaxed text-[var(--text-default)]">
      {paragraphs.map((p) => (
        <p key={p} className={/^STOP:/i.test(p) ? "font-semibold" : undefined}>
          {p}
        </p>
      ))}
    </div>
  );
}

function linkButton(href: string, label: string, primary = false) {
  return (
    <Link href={href} className="!no-underline">
      <Button type="button" variant={primary ? "primary" : "secondary"} className={primary ? BUTTON_COMPACT : BUTTON_SECONDARY}>
        {label}
      </Button>
    </Link>
  );
}

/** Next gate, publication state and the action that moves the candidate on. */
function CandidateLifecycle({ skill }: { skill: Skill }) {
  const c = skill.candidate!;
  const blocker = reviewBlocker(skill);
  const tested = c.lastTest?.revision === c.revision;
  let nextGate = `Rerun sandbox test suite · ${c.lastTest?.fixtures ?? 18} fixtures`;
  let action = <RerunTestsButton skillId={skill.id} />;
  if (c.status === "In review") {
    nextGate = `Independent approval by ${skill.approver}`;
    action = linkButton(`${SKILLS_HOME}/${skill.id}/release`, "Open release review", true);
  } else if (!blocker) {
    nextGate = "Send for independent publication review";
    action = linkButton(`${SKILLS_HOME}/${skill.id}/tests`, "Review test results", true);
  } else if (tested && !allPassed(c.lastTest)) {
    nextGate = "Correct the definition, then rerun the suite";
  }
  return (
    <Panel title="Candidate lifecycle" className="h-fit">
      <Fact label="Author / approver">
        {skill.owner} / {skill.approver}
      </Fact>
      <Fact label="Next gate">{nextGate}</Fact>
      <Fact label="Publication">
        {c.status === "In review" ? `Awaiting ${skill.approver}` : "Blocked until all tests and review pass"}
      </Fact>
      <div className="flex flex-wrap gap-2">
        {action}
        {c.status !== "In review" ? linkButton(`${SKILLS_HOME}/new?from=${skill.id}`, "Edit candidate") : null}
      </div>
    </Panel>
  );
}

export function DefinitionSection({ skill }: { skill: Skill }) {
  const c = skill.candidate;
  if (!c) {
    const p = skill.published!;
    return (
      <div className="grid grid-cols-1 gap-5 lg:grid-cols-[minmax(0,1fr)_340px]">
        <Panel title="Published instruction contract">
          <Contract paragraphs={p.contract} />
        </Panel>
        <Panel title="Published release" className="h-fit">
          <Fact label="Owner / approver">
            {skill.owner} / {skill.approver}
          </Fact>
          <Fact label="Release">
            {p.releaseId} · Approved by {p.approvedBy} · {p.publishedOn}
          </Fact>
          <Fact label="Changes">Definitions are immutable after publication; changes start a new candidate.</Fact>
          {linkButton(`${SKILLS_HOME}/new?from=${skill.id}`, "Create next candidate", true)}
        </Panel>
      </div>
    );
  }
  return (
    <>
      {c.status === "Saved" ? (
        <Note tone="success" title="Candidate snapshot saved">
          Revision {c.revision} is retained for testing.{" "}
          {skill.published
            ? `Published ${skill.published.version} remains unchanged and active for all existing runs.`
            : "Nothing is published yet, so the skill is not available to users."}
        </Note>
      ) : null}
      <div className="grid grid-cols-1 gap-5 lg:grid-cols-[minmax(0,1fr)_340px]">
        <Panel title="Saved instruction contract">
          <Contract paragraphs={c.contract} />
          <RecordList
            label="Changes in this candidate"
            columns={[skill.published ? `Change from ${skill.published.version}` : "Change", "Saved state"]}
            rows={c.changes.map((change, i) => ({ key: change.title, title: change.title, meta: [change.detail], highlight: i === 0 }))}
          />
        </Panel>
        <CandidateLifecycle skill={skill} />
      </div>
    </>
  );
}

export function InputsOutputsSection({ skill }: { skill: Skill }) {
  const d = current(skill);
  return (
    <>
      <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
        <Panel title="Input schema">
          <div className="space-y-2.5">
            {d.inputs.map((field) => (
              <FieldBox key={field.name} label={field.name} required={field.required}>
                {field.type} · {field.rule}
              </FieldBox>
            ))}
          </div>
        </Panel>
        <Panel title="Output schema">
          <RecordList
            label="Output contracts"
            columns={["Output", "Contract", "Validation"]}
            rows={d.outputs.map((o, i) => ({ key: o.name, title: o.name, meta: [o.contract, o.validation], highlight: i === 0 }))}
          />
          <Note title="Explicit missing-evidence behavior">{d.missingEvidence}</Note>
        </Panel>
      </div>
      <Panel title="Sandbox input example">
        <FieldBox label="Illustrative fixture">{d.fixture}</FieldBox>
      </Panel>
    </>
  );
}

const ROLE_PERMISSIONS = [
  { role: "Engagement lead", run: "In permitted engagement", define: "No", approve: "No self-approval" },
  { role: "Contributor", run: "In permitted engagement", define: "No", approve: "No" },
  { role: "Practice owner", run: "Sandbox & scoped run", define: "Yes · Own skill", approve: "No own release" },
  { role: "Independent reviewer", run: "Sandbox evidence only", define: "No", approve: "Assigned release only" },
  { role: "Administrator", run: "Metadata management", define: "Route candidate", approve: "Cannot bypass checks" },
];

export function PermissionsSection({ skill }: { skill: Skill }) {
  return (
    <>
      <Panel title="Role permissions">
        <RecordList
          label="Role permissions"
          columns={["Role", "Run skill", "Define candidate", "Approve release"]}
          rows={ROLE_PERMISSIONS.map((r, i) => ({ key: r.role, title: r.role, meta: [r.run, r.define, r.approve], highlight: i === 0 }))}
        />
      </Panel>
      <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
        <Panel title="Retrieval boundary">
          <FieldBox label="Source scope">Engagement + approved library · Permission-aware</FieldBox>
          <Fact label="Run access">{current(skill).permittedRoles}</Fact>
          <Fact label="External web">Disabled</Fact>
          <Fact label="Classification">Inherited from engagement and source metadata</Fact>
        </Panel>
        <Panel title="Publishing separation" className="h-fit">
          <Note title="No self-approval">
            {skill.owner} owns the definition. {skill.approver} is the independent approver. All sandbox tests must pass
            before publication.
          </Note>
          <Fact label="Export policy">Human review required for generated artifact versions</Fact>
        </Panel>
      </div>
    </>
  );
}

export function HistorySection({ skill }: { skill: Skill }) {
  const c = skill.candidate;
  const live = skill.published?.version;
  return (
    <>
      <Panel title="Version history">
        <RecordList
          label="Version history"
          columns={["Version / event", "Actor", "Time", "Lifecycle"]}
          rows={skill.history.map((h, i) => ({ key: `${h.title}-${h.at}`, title: h.title, meta: [h.actor, h.at, h.lifecycle], highlight: i === 0 }))}
        />
      </Panel>
      <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
        <Panel title="Candidate change summary">
          {c ? (
            c.changes.map((change) => (
              <Fact key={change.title} label={change.title}>
                {change.detail}
              </Fact>
            ))
          ) : (
            <p className="text-xs text-[var(--text-muted)]">No open candidate. The published definition is unchanged.</p>
          )}
        </Panel>
        <Panel title="Immutable releases" className="h-fit">
          <Note title="Existing runs remain reproducible">
            {skill.pinnedRun && live
              ? `${skill.pinnedRun} uses published ${live}. `
              : live
                ? `Runs pin the version they used. `
                : "Nothing is published yet. "}
            {c ? `Approval of ${c.version} does not modify earlier artifacts or source locators.` : "A new release never changes earlier artifacts."}
          </Note>
        </Panel>
      </div>
    </>
  );
}
