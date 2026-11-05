"use client";

import { useParams, useSearchParams } from "next/navigation";

import { JourneyStudio } from "@/features/journey/JourneyStudio";

/** Guided, step-by-step view of a project. The classic view stays at /projects/[pid]. */
export default function ProjectJourneyPage() {
  const params = useParams();
  const searchParams = useSearchParams();
  const pid = typeof params.pid === "string" ? params.pid : Array.isArray(params.pid) ? params.pid[0] ?? "" : "";

  return <JourneyStudio pid={pid} initialRunId={searchParams.get("run")} />;
}
