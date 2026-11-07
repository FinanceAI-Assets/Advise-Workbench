"use client";

import { useState } from "react";

import { Button } from "@/components/ui/Button";
import { Select } from "@/components/ui/Select";
import { ReasonAction } from "@/components/workbench/AdminControls";
import { ErrorNote } from "@/components/workbench/PageFrame";
import { useAdminAction } from "@/hooks/useAdminConsole";
import type { LibraryQualityGatesDetail } from "@/types/api";

/** Approve and publish the candidate; disabled, with the reasons, while the server reports anything blocking it. */
export function PublishControl({ practiceId, canPublish, blockers }: { practiceId: string; canPublish: boolean; blockers: string[] }) {
  if (!canPublish) {
    return (
      <div className="space-y-2">
        <Button type="button" disabled title={blockers.join(" · ")}>
          Approve &amp; publish
        </Button>
        {blockers.length ? <p className="text-xs text-[var(--text-muted)]">{blockers.join(" · ")}</p> : null}
      </div>
    );
  }
  return (
    <ReasonAction primary label="Approve & publish" build={(reason) => ({ path: `/library/${practiceId}/publish`, body: { reason } })} />
  );
}

/**
 * Approval for an uploaded candidate: once the quality gates pass, submit it to an approver, or approve and publish it directly.
 */
export function LibraryApprovalControls({ practiceId, quality }: { practiceId: string; quality: LibraryQualityGatesDetail }) {
  const submit = useAdminAction();
  const approvers = quality.approvers ?? [];
  const [approverId, setApproverId] = useState("");
  const review = quality.review;
  const chosen = approverId || approvers[0]?.id || "";

  return (
    <div className="space-y-3 border-t border-[var(--surface-border)] pt-4">
      <div>
        <p className="text-2xs font-semibold uppercase tracking-wide text-[var(--text-muted)]">Independent approval</p>
        <p className="mt-1 text-sm text-[var(--text-default)]">
          {review
            ? `${review.state} · ${review.reviewer || "Unassigned"}${review.selfReview ? " (self-review)" : ""}`
            : "Not submitted"}
        </p>
      </div>

      {quality.canSubmit ? (
        <form
          className="space-y-2"
          onSubmit={(event) => {
            event.preventDefault();
            submit.mutate({ path: `/library/${practiceId}/submit`, body: { approverId: chosen } });
          }}
        >
          <label className="grid gap-1.5 text-sm text-[var(--text-default)]">
            <span className="text-2xs font-semibold uppercase tracking-wide text-[var(--text-muted)]">Approver</span>
            <Select value={chosen} onChange={(event) => setApproverId(event.target.value)}>
              {approvers.map((person) => (
                <option key={person.id} value={person.id}>
                  {person.name}
                </option>
              ))}
            </Select>
          </label>
          <ErrorNote error={submit.error} />
          <Button type="submit" variant="secondary" disabled={submit.isPending || !chosen}>
            {submit.isPending ? "Submitting…" : review?.state === "Changes requested" ? "Resubmit for approval" : "Submit for approval"}
          </Button>
        </form>
      ) : null}

      <PublishControl practiceId={practiceId} canPublish={Boolean(quality.canPublish)} blockers={quality.blockers ?? []} />
    </div>
  );
}
