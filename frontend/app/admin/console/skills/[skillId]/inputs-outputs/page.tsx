"use client";

import { InputsOutputsSection, SkillPageFrame, useRouteSkill, versionLabel } from "@/components/skill-management";

export default function SkillInputsOutputsPage() {
  const { skill } = useRouteSkill();
  return (
    <SkillPageFrame
      skill={skill}
      tab="inputs-outputs"
      crumb={`${skill?.name} / Inputs & outputs`}
      title={`${skill?.name}: Inputs & outputs`}
      meta={skill ? `${versionLabel(skill)} · Versioned schema and output contract` : null}
    >
      {skill ? <InputsOutputsSection skill={skill} /> : null}
    </SkillPageFrame>
  );
}
