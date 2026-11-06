"use client";

import { useState } from "react";

import { Button } from "@/components/ui/Button";
import { ErrorNote } from "@/components/workbench/PageFrame";
import { useAdminAction } from "@/hooks/useAdminConsole";

// The API records a reason for every administrative change; publishing asks the admin only to confirm.
const PUBLISH_REASON = "Approved and published from Library management";

/** Approve and publish the candidate after a confirmation; disabled, with the reasons, while the server reports anything blocking it. */
export function PublishControl({ practiceId, canPublish, blockers }: { practiceId: string; canPublish: boolean; blockers: string[] }) {
  const publish = useAdminAction();
  const [confirming, setConfirming] = useState(false);

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

  if (!confirming) {
    return (
      <Button type="button" className="whitespace-nowrap text-sm" onClick={() => setConfirming(true)}>
        Approve &amp; publish
      </Button>
    );
  }

  async function confirm() {
    await publish.mutateAsync({ path: `/library/${practiceId}/publish`, body: { reason: PUBLISH_REASON } });
    setConfirming(false);
  }

  return (
    <div className="w-full space-y-2 rounded-md bg-[var(--surface-muted)] p-3">
      <p className="text-sm font-semibold text-[var(--text-default)]">Approve &amp; publish this version?</p>
      <p className="text-xs text-[var(--text-muted)]">It becomes available to users in the Leading Practice Library. You are recorded as its approver.</p>
      <ErrorNote error={publish.error} />
      <div className="flex gap-2">
        <Button type="button" disabled={publish.isPending} className="text-sm" onClick={() => void confirm().catch(() => undefined)}>
          {publish.isPending ? "Publishing…" : "Confirm"}
        </Button>
        <Button type="button" variant="secondary" disabled={publish.isPending} className="text-sm" onClick={() => setConfirming(false)}>
          Cancel
        </Button>
      </div>
    </div>
  );
}
