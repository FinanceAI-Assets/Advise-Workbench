"use client";

import { X } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import {
  BARE_CONTROL,
  BUTTON_COMPACT,
  BUTTON_SECONDARY,
  Fact,
  FieldBox,
  Note,
  RecordList,
} from "@/components/skill-management/SkillParts";
import { Button } from "@/components/ui/Button";
import { Textarea } from "@/components/ui/Textarea";
import { releaseGates, type Skill, stamp } from "@/lib/skillManagement";

export type ReleaseResult = {
  releaseId: string;
  version: string;
  approver: string;
  at: string;
  testId: string;
  previousVersion: string | null;
  pinnedRun: string;
};

const MIN_NOTE = 10;

/**
 * Release gates, the approver's note, then the published confirmation with its audit package.
 * `skill` is the candidate under review; once released, `result` describes what was published.
 */
export function PublishDialog({
  skill,
  result,
  onPublish,
  onClose,
  onViewPublished,
}: {
  skill: Skill;
  result: ReleaseResult | null;
  onPublish: (note: string) => void;
  onClose: () => void;
  onViewPublished: () => void;
}) {
  const [note, setNote] = useState("");
  const dialogRef = useRef<HTMLDivElement>(null);
  const gates = releaseGates(skill);
  const version = result?.version ?? skill.candidate?.version ?? "";
  const ready = gates.every((g) => g.ok) && note.trim().length >= MIN_NOTE;

  useEffect(() => {
    dialogRef.current?.focus();
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" role="presentation">
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="publish-skill-title"
        tabIndex={-1}
        className="max-h-[calc(100vh-2rem)] w-full max-w-xl space-y-4 overflow-y-auto rounded-lg bg-white p-6 shadow-2xl outline-none"
      >
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2 id="publish-skill-title" className="text-lg font-semibold text-[var(--text-default)]">
              Approve &amp; publish {skill.name}
            </h2>
            <p className="mt-1 text-xs text-[var(--text-muted)]">
              Release {version} only after reviewing the candidate and test evidence.
            </p>
          </div>
          <Button type="button" variant="ghost" className="p-1.5" aria-label="Close" onClick={onClose}>
            <X size={16} aria-hidden />
          </Button>
        </div>

        {result ? (
          <>
            <Note tone="success" title={`${skill.name} ${result.version} published`}>
              Approved by {result.approver} · {result.at} · {result.releaseId}. New runs use {result.version}
              {result.pinnedRun && result.previousVersion
                ? `; ${result.pinnedRun} retains ${result.previousVersion} provenance.`
                : "."}
            </Note>
            <Fact label="Audit package">Definition hash · {result.testId} evidence · Independent approval retained</Fact>
            <div className="flex gap-2">
              <Button type="button" variant="secondary" className={BUTTON_SECONDARY} onClick={onClose}>
                Close
              </Button>
              <Button type="button" className={BUTTON_COMPACT} onClick={onViewPublished}>
                View published {result.version}
              </Button>
            </div>
          </>
        ) : (
          <form
            className="space-y-4"
            onSubmit={(event) => {
              event.preventDefault();
              if (ready) onPublish(note.trim());
            }}
          >
            <RecordList
              label="Release gates"
              columns={["Release gate", "Result"]}
              rows={gates.map((g, i) => ({
                key: g.name,
                title: g.name,
                meta: [g.ok ? g.result : `${g.result} · Not met`],
                highlight: i === 0,
              }))}
            />
            <FieldBox label="Approval note" required>
              <Textarea
                rows={2}
                required
                minLength={MIN_NOTE}
                value={note}
                onChange={(event) => setNote(event.target.value)}
                placeholder="Verified missing-baseline regression and permission tests. Approved for scoped engagement runs."
                aria-label="Approval note"
                className={BARE_CONTROL}
              />
            </FieldBox>
            <p className="text-2xs text-[var(--text-muted)]">
              Recorded for {skill.approver}, the assigned independent approver, at {stamp(new Date())}.
            </p>
            <div className="flex gap-2">
              <Button type="button" variant="secondary" className={BUTTON_SECONDARY} onClick={onClose}>
                Cancel
              </Button>
              <Button
                type="submit"
                disabled={!ready}
                title={ready ? undefined : "All release gates must be met and the approval note completed."}
                className={BUTTON_COMPACT}
              >
                Approve &amp; publish {version}
              </Button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
