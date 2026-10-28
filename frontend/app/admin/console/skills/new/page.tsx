"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";

import {
  BARE_CONTROL,
  BARE_SELECT,
  BUTTON_COMPACT,
  Fact,
  FieldBox,
  Note,
  Panel,
  SKILLS_HOME,
} from "@/components/skill-management";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Select } from "@/components/ui/Select";
import { Textarea } from "@/components/ui/Textarea";
import { PageFrame, PageSkeleton } from "@/components/workbench/PageFrame";
import { useSkillManagement } from "@/hooks/useSkillManagement";
import { CATEGORIES, type DefinitionDraft, draftFrom, emptyDraft, nextVersion, PEOPLE, validateDraft } from "@/lib/skillManagement";

const FORM_ID = "define-skill-form";

function DefineSkill() {
  const params = useSearchParams();
  const router = useRouter();
  const { skill, createSkill, saveCandidate } = useSkillManagement();
  const base = skill(params.get("from") ?? "");
  const [draft, setDraft] = useState<DefinitionDraft>(() => (base ? draftFrom(base) : emptyDraft()));
  const [attempted, setAttempted] = useState(false);
  const check = validateDraft(draft);
  const set = (field: keyof DefinitionDraft) => (event: { target: { value: string } }) =>
    setDraft((current) => ({ ...current, [field]: event.target.value }));

  const version = base?.candidate?.version ?? nextVersion(base?.published?.version);
  const title = base ? (base.candidate ? `Edit candidate: ${base.name}` : `Define next candidate: ${base.name}`) : "Define a new skill";

  function submit(event: React.FormEvent) {
    event.preventDefault();
    setAttempted(true);
    if (!check.ok) return;
    if (base) {
      saveCandidate(base.id, draft);
      router.push(`${SKILLS_HOME}/${base.id}`);
    } else {
      router.push(`${SKILLS_HOME}/${createSkill(draft)}`);
    }
  }

  return (
    <PageFrame
      breadcrumb={`Admin console / Skills management / ${base ? `${base.name} / New candidate` : "New skill"}`}
      title={title}
      subtitle="Create an evidence contract, test behavior and require independent approval before publishing."
      actions={
        <Button type="submit" form={FORM_ID} className={BUTTON_COMPACT}>
          Save candidate
        </Button>
      }
    >
      <form id={FORM_ID} onSubmit={submit} noValidate className="grid grid-cols-1 gap-5 lg:grid-cols-[minmax(0,1fr)_340px]">
        <Panel title="Candidate definition" className="h-fit">
          <div className="grid gap-3 sm:grid-cols-2">
            <FieldBox label="Skill name" required>
              <Input
                aria-label="Skill name"
                value={draft.name}
                onChange={set("name")}
                disabled={Boolean(base)}
                placeholder="Pilot adoption assessor"
                className={BARE_CONTROL}
              />
            </FieldBox>
            <FieldBox label="Category">
              <Select aria-label="Category" value={draft.category} onChange={set("category")} className={BARE_SELECT}>
                {CATEGORIES.map((c) => (
                  <option key={c}>{c}</option>
                ))}
              </Select>
            </FieldBox>
          </div>
          <FieldBox label="Instruction contract" required>
            <Textarea
              aria-label="Instruction contract"
              rows={3}
              value={draft.contract}
              onChange={set("contract")}
              placeholder="ROLE: Evidence-led adoption analyst. INPUT: Pilot brief, adoption baseline and permitted evidence. METHOD: Assess adoption, identify gaps and recommend next steps. STOP: Ask for missing baselines. OUTPUT: Source-linked DOCX. REVIEW: Human approval before export."
              className={BARE_CONTROL}
            />
          </FieldBox>
          <FieldBox label="Input schema" required>
            <Input
              aria-label="Input schema"
              value={draft.inputSchema}
              onChange={set("inputSchema")}
              placeholder="brief:string · sources:Source[] · baseline:Measure[]"
              className={BARE_CONTROL}
            />
          </FieldBox>
          <FieldBox label="Output schema" required>
            <Input
              aria-label="Output schema"
              value={draft.outputSchema}
              onChange={set("outputSchema")}
              placeholder="DOCX / 4 pages · Evidence register · Assumption list"
              className={BARE_CONTROL}
            />
          </FieldBox>
          <FieldBox label="Permitted roles">
            <Input
              aria-label="Permitted roles"
              value={draft.permittedRoles}
              onChange={set("permittedRoles")}
              placeholder="Engagement lead, Contributor · Scoped engagement only"
              className={BARE_CONTROL}
            />
          </FieldBox>
        </Panel>

        <Panel title="Ownership & safety" className="h-fit">
          <FieldBox label="Owner">
            <Select aria-label="Owner" value={draft.owner} onChange={set("owner")} className={BARE_SELECT}>
              {PEOPLE.map((p) => (
                <option key={p}>{p}</option>
              ))}
            </Select>
          </FieldBox>
          <FieldBox label="Independent approver">
            <Select aria-label="Independent approver" value={draft.approver} onChange={set("approver")} className={BARE_SELECT}>
              {PEOPLE.map((p) => (
                <option key={p}>{p}</option>
              ))}
            </Select>
          </FieldBox>
          <Fact label={base ? "Candidate version" : "Initial version"}>
            {version} candidate ·{" "}
            {base?.published ? `Published ${base.published.version} stays active` : "Not available to users"}
          </Fact>
          {check.ok ? (
            <Note tone="success" title="Definition validation">
              Required fields complete. Missing-evidence stop rule and human approval are explicit.
            </Note>
          ) : (
            <Note tone={attempted ? "warning" : "muted"} title="Definition validation">
              <ul className="list-disc space-y-0.5 pl-4">
                {check.problems.map((p) => (
                  <li key={p}>{p}</li>
                ))}
              </ul>
            </Note>
          )}
          <Note title="Next step: sandbox tests">
            Saving creates a versioned candidate; it does not publish the skill or alter active runs.
          </Note>
        </Panel>
      </form>
    </PageFrame>
  );
}

export default function DefineSkillPage() {
  // ?from=<skill> starts the next candidate of a published skill; it needs a Suspense boundary to render statically.
  return (
    <Suspense fallback={<PageSkeleton />}>
      <DefineSkill />
    </Suspense>
  );
}
