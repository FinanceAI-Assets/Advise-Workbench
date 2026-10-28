"use client";

import { Suspense } from "react";

import { PublishedRegistry } from "@/components/skill-management";
import { PageSkeleton } from "@/components/workbench/PageFrame";

export default function SkillRegistryPage() {
  // The selected skill is read from ?skill=, which needs a Suspense boundary for static rendering.
  return (
    <Suspense fallback={<PageSkeleton />}>
      <PublishedRegistry />
    </Suspense>
  );
}
