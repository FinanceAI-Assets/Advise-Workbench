"use client";

import { Check, Loader2 } from "lucide-react";
import Link from "next/link";

import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { ErrorNote } from "@/components/workbench/PageFrame";
import { useApproveRunMutation, useRunProgressQuery } from "@/hooks/useWorkbench";
import { cn } from "@/lib/utils";

function duration(seconds: number): string {
  const minutes = Math.floor(seconds / 60);
  return minutes > 0 ? `${minutes} min ${seconds % 60}s` : `${seconds}s`;
}

/**
 * Progress of the engagement's latest draft generation: the milestones reached, the one in
 * progress, and the next thing to do (approve the plan, wait, or open the drafts for review).
 */
export function RunProgressCard({ pid, showArtifactsLink = true }: { pid: string; showArtifactsLink?: boolean }) {
  const progress = useRunProgressQuery(pid);
  const approve = useApproveRunMutation(pid);
  const run = progress.data?.run;
  if (!run) return null;

  // Generation that stopped after writing its files still left usable drafts.
  const stoppedWithFiles = run.failed && run.outputs.length > 0;
  const title = stoppedWithFiles
    ? "Drafts were produced, but the final checks did not finish"
    : run.needsApproval
    ? "A plan is ready for your approval"
    : run.active
      ? "Generating your drafts"
      : run.finished
        ? "Drafts are ready for review"
        : run.failed
          ? "Draft generation stopped"
          : `Latest run: ${run.status.replaceAll("_", " ")}`;

  return (
    <Card
      className={cn(
        "space-y-3",
        stoppedWithFiles
          ? "border-[#F3E2C0] bg-[#FCF3E2]"
          : run.failed
            ? "border-[#E8B4AE] bg-[#FBEFEB]"
            : run.finished ? "border-[var(--accent-green)] bg-[#EFF6E6]" : ""
      )}
      aria-live="polite"
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="flex items-center gap-2 text-sm font-semibold text-[var(--text-default)]">
            {run.active ? <Loader2 size={16} className="animate-spin text-[var(--accent-green-dark)]" aria-hidden /> : null}
            {title}
          </p>
          <p className="text-xs text-[var(--text-muted)]">
            {run.id}
            {run.active ? ` · running for ${duration(run.elapsedSeconds)}` : ""}
            {run.active && run.lastUpdateSeconds > 90 ? ` · last update ${duration(run.lastUpdateSeconds)} ago` : ""}
            {run.finished ? ` · took ${duration(run.elapsedSeconds)}` : ""}
          </p>
        </div>
        <div className="flex shrink-0 flex-wrap items-center gap-2">
          {run.needsApproval ? (
            <Button disabled={approve.isPending} onClick={() => approve.mutate(run.id)}>
              {approve.isPending ? "Starting…" : "Approve plan and generate"}
            </Button>
          ) : null}
          {showArtifactsLink && (run.finished || run.active || stoppedWithFiles) ? (
            <Link href={`/engagements/${pid}/deliverables`} className="!no-underline">
              <Button variant={run.finished ? "primary" : "secondary"}>
                {run.finished ? "Open drafts and submit for review" : "View artifacts"}
              </Button>
            </Link>
          ) : null}
        </div>
      </div>

      {run.active || run.finished ? (
        <ol className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
          {run.stages.map((stage) => (
            <li key={stage.id} className="flex items-center gap-2 text-sm">
              <span
                className={cn(
                  "flex h-5 w-5 shrink-0 items-center justify-center rounded-full border text-2xs",
                  stage.state === "done" && "border-[var(--accent-green)] bg-[var(--accent-green)] text-white",
                  stage.state === "current" && "border-[var(--accent-green)] text-[var(--accent-green-dark)]",
                  stage.state === "upcoming" && "border-[var(--surface-border)] text-[var(--text-muted)]"
                )}
              >
                {stage.state === "done" ? (
                  <Check size={12} aria-hidden />
                ) : stage.state === "current" ? (
                  <Loader2 size={12} className="animate-spin" aria-hidden />
                ) : null}
              </span>
              <span
                className={cn(
                  stage.state === "upcoming" ? "text-[var(--text-muted)]" : "text-[var(--text-default)]",
                  stage.state === "current" && "font-semibold"
                )}
              >
                {stage.label}
              </span>
            </li>
          ))}
        </ol>
      ) : null}

      {run.active ? (
        <p className="text-xs text-[var(--text-muted)]">
          This usually takes several minutes. You can leave this page; you&apos;ll get a notification when the drafts are
          ready.
        </p>
      ) : null}
      {run.finished ? (
        <p className="text-xs text-[var(--text-muted)]">
          Next: open the drafts, check them, and choose Submit for review. Downloads unlock once a reviewer approves.
        </p>
      ) : null}
      {stoppedWithFiles ? (
        <p className="text-sm text-[#8C5B12]">
          Check the drafts before using them ({run.outputs.join(" and ").toUpperCase()} available). Reason the checks
          stopped: {run.error || "not recorded"}.
        </p>
      ) : run.failed ? (
        <p className="text-sm text-[#A53E37]">{run.error || "The run failed without a recorded reason."}</p>
      ) : null}
      <ErrorNote error={approve.error ?? progress.error} />
    </Card>
  );
}
