"use client";

import { Suspense } from "react";

import { CandidateRegistry } from "@/components/skill-management";
import { PageSkeleton } from "@/components/workbench/PageFrame";

export default function SkillCandidatesPage() {
  return (
    <Suspense fallback={<PageSkeleton />}>
      <CandidateRegistry />
    </Suspense>
  );
}
