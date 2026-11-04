"use client";

import Link from "next/link";
import { useState } from "react";

import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { Field } from "@/components/workbench/PageFrame";
import type { RegisterClaim } from "@/hooks/useDeliverables";
import { cn } from "@/lib/utils";

const LIBRARY_ID = /\blp-\d+\b/i;

/** Where a claim's support comes from: the approved library, the engagement's own sources, or nowhere yet. */
function classification(claim: RegisterClaim): string {
  if (!claim.citation) return "Assumption";
  return LIBRARY_ID.test(claim.citation) ? "Approved library" : "Engagement source";
}

/** Evidence register tab: claim-to-source links, the selected citation, and coverage of the run's claims. */
export function EvidenceRegisterView({
  pid,
  claims,
  sourceCount,
  evaluatedAt,
  outputs,
}: {
  pid: string;
  claims: RegisterClaim[];
  sourceCount: number;
  evaluatedAt: string;
  outputs: string;
}) {
  const [selectedId, setSelectedId] = useState("");
  if (claims.length === 0) {
    return (
      <EmptyState
        title="No claims recorded"
        description="This run has no evidence checks yet. Claims appear here once the deck has been validated against its sources."
      />
    );
  }
  const selected = claims.find((c) => c.id === selectedId) ?? claims[0];
  const supported = claims.filter((c) => c.grounded).length;
  const unsupported = claims.length - supported;
  const libraryId = LIBRARY_ID.exec(selected.citation)?.[0]?.toLowerCase();
  const sourceHref = libraryId ? `/library?practice=${libraryId}` : `/engagements/${pid}?tab=sources`;

  return (
    <div className="space-y-4">
      <Card className="space-y-3">
        <div className="flex flex-wrap items-baseline gap-2">
          <h2 className="text-base font-semibold text-[var(--text-default)]">Claim-to-source links</h2>
          <span className="text-xs text-[var(--text-muted)]">
            · {claims.length} claim{claims.length === 1 ? "" : "s"} from this run
          </span>
        </div>
        <div className="rounded-lg border border-[var(--surface-border)]">
          <p className="border-b border-[var(--surface-border)] px-4 py-2 text-2xs font-semibold uppercase tracking-wide text-[var(--text-muted)]">
            Claim / artifact · Source / locator · Classification · Validation
          </p>
          <ul className="max-h-[420px] divide-y divide-[var(--surface-border)] overflow-y-auto">
            {claims.map((claim) => {
              const active = claim.id === selected.id;
              return (
                <li key={claim.id}>
                  <button
                    type="button"
                    onClick={() => setSelectedId(claim.id)}
                    aria-current={active ? "true" : undefined}
                    className={cn(
                      "w-full px-4 py-2.5 text-left transition",
                      active ? "bg-[#EFF6E6]" : "hover:bg-[var(--surface-muted)]"
                    )}
                  >
                    <span
                      className={cn(
                        "block text-sm font-semibold",
                        active ? "text-[var(--accent-green-dark)]" : "text-[var(--text-default)]"
                      )}
                    >
                      {claim.claim} · Slide {claim.slide}
                    </span>
                    <span className="block text-xs text-[var(--text-muted)]">
                      {claim.citation || "No supporting source"} · {classification(claim)} ·{" "}
                      <span className={claim.grounded ? "text-[#356B12]" : "text-[#8C5B12]"}>
                        {claim.grounded ? "Verified" : "Needs caveat"}
                      </span>
                    </span>
                  </button>
                </li>
              );
            })}
          </ul>
        </div>
      </Card>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card className="space-y-4">
          <h2 className="text-base font-semibold text-[var(--text-default)]">Selected citation</h2>
          <Field label="Passage">{selected.context || selected.claim}</Field>
          <Field label="Provenance">
            {selected.citation || "No supporting source"} · Slide {selected.slide} · {selected.slideTitle}
            {selected.claimType ? ` · ${selected.claimType}` : ""}
          </Field>
          {selected.citation ? (
            <Link href={sourceHref} className="inline-block !no-underline">
              <Button type="button" variant="secondary">
                Open permitted source
              </Button>
            </Link>
          ) : (
            <p className="text-xs text-[var(--text-muted)]">
              Add a source for this claim, or state it as an explicit assumption before resubmission.
            </p>
          )}
        </Card>

        <Card className="space-y-4">
          <h2 className="text-base font-semibold text-[var(--text-default)]">Coverage &amp; integrity</h2>
          <div
            className={cn(
              "rounded-lg border p-3",
              unsupported ? "border-[#F3E2C0] bg-[#FCF3E2] text-[#8C5B12]" : "border-[var(--surface-border)] bg-[#EFF6E6] text-[#356B12]"
            )}
          >
            <p className="text-sm font-semibold">
              {supported} of {claims.length} claims supported
            </p>
            <p className="text-xs">
              {unsupported
                ? `${unsupported} claim${unsupported === 1 ? " is" : "s are"} not validated. Replace ${unsupported === 1 ? "it" : "them"} with a source or an explicit assumption before resubmission.`
                : "Every claim in this run is linked to a permitted source."}
            </p>
          </div>
          <Field label="Source permissions">
            {sourceCount} permitted source{sourceCount === 1 ? "" : "s"}
            {evaluatedAt ? ` · Evaluated ${evaluatedAt}` : ""}
          </Field>
          <Field label="Outputs">{outputs}</Field>
        </Card>
      </div>
    </div>
  );
}
