"use client";

import { PermissionsSection, SkillPageFrame, useRouteSkill, versionLabel } from "@/components/skill-management";

export default function SkillPermissionsPage() {
  const { skill } = useRouteSkill();
  return (
    <SkillPageFrame
      skill={skill}
      tab="permissions"
      crumb={`${skill?.name} / Permissions`}
      title={`${skill?.name}: Permissions`}
      meta={skill ? `${versionLabel(skill)} · Run, define and approve permissions are separated.` : null}
    >
      {skill ? <PermissionsSection skill={skill} /> : null}
    </SkillPageFrame>
  );
}
