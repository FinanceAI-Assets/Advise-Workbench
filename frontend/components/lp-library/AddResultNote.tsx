import Link from "next/link";

import type { AddPracticesResult } from "@/hooks/useWorkbench";

export const engagementSourcesPath = (projectId: string) => `/engagements/${encodeURIComponent(projectId)}?tab=sources`;

/** What came of adding sources to an engagement: where they went, and what could not be added. */
export function AddResultNote({
  result,
  projectId,
  projectName,
  failedHint,
}: {
  result: AddPracticesResult;
  projectId: string;
  projectName: string;
  failedHint: string;
}) {
  const placed = result.added.length + result.already.length;
  return (
    <>
      {placed ? (
        <p className="text-sm text-[#356B12]" role="status">
          {result.added.length
            ? `${result.added.length} source${result.added.length === 1 ? "" : "s"} added to ${projectName}.`
            : `Already in ${projectName}'s sources.`}
          {result.added.length && result.already.length ? ` ${result.already.length} already there.` : ""}{" "}
          <Link href={engagementSourcesPath(projectId)} className="font-medium underline">
            View engagement sources
          </Link>
        </p>
      ) : null}
      {result.failed.length ? (
        <p role="alert" className="text-sm text-[var(--status-failed-text)]">
          {failedHint} {result.failed[0].message}
          {result.failed.length > 1 ? ` (and ${result.failed.length - 1} more)` : ""}
        </p>
      ) : null}
    </>
  );
}
