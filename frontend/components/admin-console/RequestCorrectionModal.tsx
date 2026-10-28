"use client";

import { X } from "lucide-react";
import { type FormEvent, useEffect, useRef, useState } from "react";

import { Callout } from "@/components/admin-console/LibraryPipelineTabs";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Textarea } from "@/components/ui/Textarea";
import { ErrorNote } from "@/components/workbench/PageFrame";
import { useAdminAction } from "@/hooks/useAdminConsole";
import { useAuth } from "@/lib/auth-context";
import type { LibraryCorrectionDraft } from "@/types/api";

// Form controls inherit the label's font (globals.css), so the caption styling sits on a span.
const FIELD_LABEL = "grid gap-1.5 text-sm text-[var(--text-default)]";
const FIELD_CAPTION = "text-2xs font-semibold uppercase tracking-wide text-[var(--text-muted)]";

function formatDate(value: string) {
  const date = new Date(`${value}T00:00:00`);
  return Number.isNaN(date.getTime())
    ? value
    : date.toLocaleDateString("en-GB", { day: "2-digit", month: "short", year: "numeric" });
}

/** Sends a publication-blocking correction to the practice owner. The candidate stays unpublished. */
export function RequestCorrectionModal({
  practiceId,
  draft,
  onClose,
  onSent,
}: {
  practiceId: string;
  draft: LibraryCorrectionDraft;
  onClose: () => void;
  onSent: (correctionId: string) => void;
}) {
  const { user } = useAuth();
  const action = useAdminAction();
  const [assignee, setAssignee] = useState(draft.assignee);
  const [due, setDue] = useState(draft.due);
  const [sourceLocation, setSourceLocation] = useState(draft.sourceLocation);
  const [requiredCorrection, setRequiredCorrection] = useState(draft.requiredCorrection);
  const [sent, setSent] = useState<{ id: string; at: Date } | null>(null);
  const dialogRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    dialogRef.current?.focus();
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [onClose]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    const result = (await action.mutateAsync({
      path: `/library/${practiceId}/request-correction`,
      body: {
        reason: requiredCorrection.trim(),
        source_location: sourceLocation.trim(),
        severity: draft.severity,
        assignee: assignee.trim(),
        due: formatDate(due),
      },
    })) as { correctionId?: string };
    const id = result.correctionId ?? "Correction";
    setSent({ id, at: new Date() });
    onSent(id);
  }

  return (
    <div
      className="fixed inset-0 z-[60] flex items-center justify-center bg-black/45 p-4"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="request-correction-title"
        aria-describedby="request-correction-description"
        tabIndex={-1}
        className="max-h-[calc(100vh-2rem)] w-full max-w-xl overflow-y-auto rounded-lg bg-[var(--surface-default)] p-5 shadow-2xl outline-none"
      >
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2 id="request-correction-title" className="text-lg font-semibold text-[var(--text-default)]">
              Request a source correction
            </h2>
            <p id="request-correction-description" className="mt-1 text-sm text-[var(--text-muted)]">
              Send an actionable issue to the practice owner. The candidate remains unpublished.
            </p>
          </div>
          <Button type="button" variant="ghost" className="p-2" aria-label="Close correction dialog" onClick={onClose}>
            <X size={18} aria-hidden />
          </Button>
        </div>

        <form className="mt-5 space-y-4" onSubmit={(event) => void submit(event)}>
          <fieldset disabled={Boolean(sent) || action.isPending} className="space-y-4">
            <div className="grid gap-3 sm:grid-cols-[1fr_180px]">
              <label className={FIELD_LABEL}>
                <span className={FIELD_CAPTION}>Assignee</span>
                <Input required value={assignee} onChange={(event) => setAssignee(event.target.value)} />
              </label>
              <label className={FIELD_LABEL}>
                <span className={FIELD_CAPTION}>Due</span>
                <Input required type="date" value={due} onChange={(event) => setDue(event.target.value)} />
              </label>
            </div>
            <label className={FIELD_LABEL}>
              <span className={FIELD_CAPTION}>Source location</span>
              <Input value={sourceLocation} onChange={(event) => setSourceLocation(event.target.value)} />
            </label>
            <label className={FIELD_LABEL}>
              <span className={FIELD_CAPTION}>
                Required correction <span aria-hidden>*</span>
              </span>
              <Textarea
                required
                minLength={5}
                rows={4}
                value={requiredCorrection}
                onChange={(event) => setRequiredCorrection(event.target.value)}
                className="rounded-md"
              />
            </label>
          </fieldset>

          <div>
            <p className="text-2xs font-semibold uppercase tracking-wide text-[var(--text-muted)]">Severity</p>
            <p className="mt-1 text-sm text-[var(--text-default)]">{draft.severity}</p>
          </div>

          {sent ? (
            <Callout
              tone="success"
              notice={{
                title: `Correction request sent · ${sent.id}`,
                description: `${user?.name ?? "You"} requested correction on ${sent.at.toLocaleString("en-GB", {
                  day: "2-digit",
                  month: "short",
                  hour: "2-digit",
                  minute: "2-digit",
                })}. ${assignee} has been notified. The published baseline remains active.`,
              }}
            />
          ) : null}
          <ErrorNote error={action.error} />

          <div className="flex justify-end gap-2 border-t border-[var(--surface-border)] pt-4">
            <Button type="button" variant="secondary" onClick={onClose}>
              Cancel
            </Button>
            {sent ? (
              <Button type="button" onClick={onClose}>
                Return to quality review
              </Button>
            ) : (
              <Button type="submit" disabled={action.isPending}>
                {action.isPending ? "Sending…" : "Send correction request"}
              </Button>
            )}
          </div>
        </form>
      </div>
    </div>
  );
}
