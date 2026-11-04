"use client";

import { HistorySection, SkillPageFrame, useRouteSkill } from "@/components/skill-management";

export default function SkillHistoryPage() {
  const { skill } = useRouteSkill();
  return (
    <SkillPageFrame
      skill={skill}
      tab="history"
      crumb={`${skill?.name} / History`}
      title={`${skill?.name}: History`}
      meta={skill ? `${skill.code} · Versioned definitions, test evidence and publication decisions.` : null}
    >
      {skill ? <HistorySection skill={skill} /> : null}
    </SkillPageFrame>
  );
}
