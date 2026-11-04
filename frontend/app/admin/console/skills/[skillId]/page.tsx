"use client";

import { DefinitionSection, SkillPageFrame, useRouteSkill, versionLabel } from "@/components/skill-management";

export default function SkillDefinitionPage() {
  const { skill } = useRouteSkill();
  const c = skill?.candidate;
  const justSaved = c?.status === "Saved";
  return (
    <SkillPageFrame
      skill={skill}
      tab="definition"
      crumb={justSaved ? "Save candidate" : `${skill?.name} / Definition`}
      title={justSaved ? `${skill?.name} candidate saved` : `${skill?.name}: Definition`}
      meta={skill ? `${versionLabel(skill)} · Owner: ${skill.owner}${c ? ` · ${c.savedAt}` : ""}` : null}
    >
      {skill ? <DefinitionSection skill={skill} /> : null}
    </SkillPageFrame>
  );
}
