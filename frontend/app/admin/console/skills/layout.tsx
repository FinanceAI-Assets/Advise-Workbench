"use client";

import type { ReactNode } from "react";

import { PageSkeleton } from "@/components/workbench/PageFrame";
import { SkillManagementProvider, useSkillManagement } from "@/hooks/useSkillManagement";

// Skill pages wait for the session's saved registry, so a skill created earlier in the session is found.
function WhenReady({ children }: { children: ReactNode }) {
  const { ready } = useSkillManagement();
  return ready ? children : <PageSkeleton />;
}

/** Skill management keeps its registry in the browser; every page under /admin/console/skills shares it. */
export default function SkillsLayout({ children }: { children: ReactNode }) {
  return (
    <SkillManagementProvider>
      <WhenReady>{children}</WhenReady>
    </SkillManagementProvider>
  );
}
