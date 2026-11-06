"use client";

import { Check, X } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/Button";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { Textarea } from "@/components/ui/Textarea";
import { ErrorNote } from "@/components/workbench/PageFrame";
import type { ArtifactDesignReview } from "@/hooks/usePhase5Review";

/**
 * Final approve or reject for an artifact reviewed as a whole (anything but a deck), each after a confirmation.
 * Rejecting regenerates the whole artifact with the reviewer's feedback. Only available while the run waits in
 * design review.
 */
export function ArtifactApproval({ label, design }: { label: string; design: ArtifactDesignReview | null }) {
  const [confirming, setConfirming] = useState<"approve" | "reject" | null>(null);
  const [feedback, setFeedback] = useState("");
  const live = design?.waiting && !design.approved && !design.regenerating ? design : null;

  const unavailable = !design
    ? "This run has no design review, so there is nothing to approve."
    : design.approved
      ? null
      : design.regenerating
        ? null
        : !design.waiting
          ? "This run is no longer waiting for a decision."
          : null;

  async function confirm() {
    if (!live || !confirming) return;
    try {
      if (confirming === "approve") await live.approve();
      else await live.reject(null, feedback);
    } catch {
      // The request failed: nothing changes, and the error is shown below.
    } finally {
      setConfirming(null);
      setFeedback("");
    }
  }

  return (
    <div className="space-y-2 border-t border-[var(--surface-border)] pt-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-xs text-[var(--text-muted)]" aria-live="polite">
          <span className="font-semibold text-[var(--text-default)]">Final decision</span>
          {design ? ` · ${label} ${design.version}` : ""}
        </p>
        <div className="flex items-center gap-2">
          <Button
            type="button"
            className="flex items-center gap-2 text-sm"
            disabled={!live || live.busy}
            title={design?.approved ? `${label} is approved` : unavailable ?? undefined}
            onClick={() => setConfirming("approve")}
          >
            <Check size={16} aria-hidden />
            Approve
          </Button>
          <Button
            type="button"
            variant="secondary"
            className="flex items-center gap-2 text-sm"
            disabled={!live || live.busy || Boolean(live.rejectBlocked)}
            title={live?.rejectBlocked ?? unavailable ?? undefined}
            onClick={() => setConfirming("reject")}
          >
            <X size={16} aria-hidden />
            Reject
          </Button>
        </div>
      </div>
      {design?.approved ? <p className="text-xs text-[#356B12]">{label} {design.version} approved.</p> : null}
      {unavailable ? <p className="text-xs text-[var(--text-muted)]">{unavailable}</p> : null}
      <ErrorNote error={design?.error} />
      {confirming ? (
        <ConfirmDialog
          title={confirming === "approve" ? `Approve the ${label.toLowerCase()}?` : `Send the ${label.toLowerCase()} back?`}
          description={
            confirming === "approve"
              ? `${label} ${design?.version ?? ""} will be approved. This cannot be undone.`
              : `The whole ${label.toLowerCase()} will be regenerated.`
          }
          confirmLabel={confirming === "approve" ? "Approve" : "Reject"}
          busy={Boolean(live?.busy)}
          onCancel={() => setConfirming(null)}
          onConfirm={() => void confirm()}
        >
          {confirming === "reject" ? (
            <label className="grid gap-1.5 text-2xs font-semibold uppercase tracking-wide text-[var(--text-muted)]">
              What should change (optional)
              <Textarea
                rows={3}
                value={feedback}
                onChange={(e) => setFeedback(e.target.value)}
                placeholder="For example: shorten the executive summary"
              />
            </label>
          ) : null}
        </ConfirmDialog>
      ) : null}
    </div>
  );
}
