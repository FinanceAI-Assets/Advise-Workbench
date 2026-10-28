"use client";

import Link from "next/link";

import { ExportApprovalNotice } from "@/components/deliverables/ExportApprovalNotice";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { Skeleton } from "@/components/ui/Skeleton";
import { ErrorNote, Field } from "@/components/workbench/PageFrame";
import { useDeliverablesQuery } from "@/hooks/useDeliverables";
import { useExportReadinessQuery } from "@/hooks/useEngagements";
import { cn } from "@/lib/utils";
import type { EngagementDetail } from "@/types/api";

const STATE_CLASS: Record<string, string> = {
  "Changes requested": "text-[#8C5B12]",
  Approved: "text-[#356B12]",
  "In review": "text-[var(--accent-blue)]",
};

export function formatRunTime(iso: string | null): string {
  if (!iso) return "";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleString("en-GB", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" });
}

/** Engagement page, Deliverables tab: the latest run's artifacts at a glance, linking into each artifact's view. */
export function DeliverablesOverview({ id, detail }: { id: string; detail: EngagementDetail }) {
  const deliverables = useDeliverablesQuery(id);
  const readiness = useExportReadinessQuery(id);
  const base = `/engagements/${id}/deliverables`;

  if (deliverables.isPending) return <Skeleton className="h-72 w-full" />;
  if (!deliverables.data) {
    return (
      <>
        <ErrorNote error={deliverables.error} />
        <EmptyState title="No deliverables yet" description="Start a conversation and approve a plan to generate the first drafts.">
          <Link href={`/engagements/${id}/conversation`}>
            <Button type="button">Open conversation</Button>
          </Link>
        </EmptyState>
      </>
    );
  }

  const data = deliverables.data;
  const reviews = (readiness.data?.artifacts ?? []).filter((a) => a.runId === data.runId);
  const reviewOf = (kind: string) => reviews.find((a) => a.type === kind);
  const state = (kind: "pptx" | "docx") => reviewOf(kind)?.review ?? data[kind].status;
  const name = (kind: "pptx" | "docx") => reviewOf(kind)?.name ?? data[kind].name;
  const version = (kind: "pptx" | "docx") => reviewOf(kind)?.version.split(" ").pop() ?? data[kind].versionLabel.split(" ").pop();
  const hasPptx = data.tabCounts.powerpoint > 0;
  const hasDocx = data.tabCounts.word > 0;
  const supported = data.claims.filter((c) => c.grounded).length;
  const locked = (["pptx", "docx"] as const).filter((kind) => data.tabCounts[kind === "pptx" ? "powerpoint" : "word"] && state(kind) !== "Approved");

  const rows = [
    hasPptx && {
      tab: "powerpoint",
      name: name("pptx"),
      meta: `PPTX · ${data.pptx.slides.length} slides · ${version("pptx")}`,
      state: state("pptx"),
    },
    hasDocx && {
      tab: "word",
      name: name("docx"),
      meta: `DOCX · ${data.docx.preview.sections.length} sections · ${version("docx")}`,
      state: state("docx"),
    },
    data.claims.length && {
      tab: "evidence-register",
      name: "Evidence register",
      meta: `${data.claims.length} claims · ${supported} supported`,
      state: "Current",
    },
  ].filter(Boolean) as Array<{ tab: string; name: string; meta: string; state: string }>;

  return (
    <section className="space-y-4">
      <Card className="space-y-3">
        <div className="flex flex-wrap items-baseline gap-2">
          <h2 className="text-base font-semibold text-[var(--text-default)]">Conversation artifacts</h2>
          <span className="text-xs text-[var(--text-muted)]">
            · {detail.code} · {data.runId.toUpperCase()}
          </span>
        </div>
        <div className="rounded-lg border border-[var(--surface-border)]">
          <p className="border-b border-[var(--surface-border)] px-4 py-2 text-2xs font-semibold uppercase tracking-wide text-[var(--text-muted)]">
            Artifact · Format / version · Owner · Review state
          </p>
          <ul className="divide-y divide-[var(--surface-border)]">
            {rows.map((row, i) => (
              <li key={row.tab}>
                <Link href={`${base}?tab=${row.tab}`} className="block px-4 py-2.5 !no-underline hover:bg-[var(--surface-muted)]">
                  <span className={cn("block text-sm font-semibold", i === 0 ? "text-[var(--accent-green-dark)]" : "text-[var(--text-default)]")}>
                    {row.name}
                  </span>
                  <span className="block text-xs text-[var(--text-muted)]">
                    {row.meta} · {detail.lead} · <span className={STATE_CLASS[row.state]}>{row.state}</span>
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        </div>
      </Card>

      <div className="grid gap-4 lg:grid-cols-3">
        <Card className="space-y-3">
          <h2 className="text-base font-semibold text-[var(--text-default)]">PowerPoint draft</h2>
          {hasPptx ? (
            <>
              <div>
                <p className="text-sm font-semibold text-[var(--text-default)]">
                  {name("pptx")} <span className={cn("ml-1 text-xs font-medium", STATE_CLASS[state("pptx")])}>{state("pptx")}</span>
                </p>
                <p className="text-xs text-[var(--text-muted)]">
                  PPTX · {data.pptx.slides.length} slides · {version("pptx")}
                </p>
              </div>
              <div className="flex flex-wrap gap-2">
                <Link href={`${base}?tab=powerpoint`}>
                  <Button type="button" variant="secondary">
                    Open PowerPoint
                  </Button>
                </Link>
                {reviewOf("pptx") ? (
                  <Link href={`/reviews/${encodeURIComponent(reviewOf("pptx")!.id)}`}>
                    <Button type="button" variant="secondary">
                      Open review
                    </Button>
                  </Link>
                ) : null}
              </div>
            </>
          ) : (
            <p className="text-xs text-[var(--text-muted)]">This run did not produce a deck.</p>
          )}
        </Card>

        <Card className="space-y-3">
          <h2 className="text-base font-semibold text-[var(--text-default)]">Word draft</h2>
          {hasDocx ? (
            <>
              <div>
                <p className="text-sm font-semibold text-[var(--text-default)]">
                  {name("docx")} <span className={cn("ml-1 text-xs font-medium", STATE_CLASS[state("docx")])}>{state("docx")}</span>
                </p>
                <p className="text-xs text-[var(--text-muted)]">
                  DOCX · {data.docx.preview.sections.length} sections · {version("docx")} · {data.docx.citationSummary}
                </p>
              </div>
              <Link href={`${base}?tab=word`}>
                <Button type="button" variant="secondary">
                  Open Word
                </Button>
              </Link>
            </>
          ) : (
            <p className="text-xs text-[var(--text-muted)]">This run did not produce a document.</p>
          )}
        </Card>

        <Card className="space-y-3">
          <h2 className="text-base font-semibold text-[var(--text-default)]">Provenance</h2>
          <Field label="Generation">
            {data.runId.toUpperCase()}
            {formatRunTime(data.run.createdAt) ? ` · ${formatRunTime(data.run.createdAt)}` : ""}
          </Field>
          <Field label="Source scope">
            {detail.tabCounts.sources} permitted source{detail.tabCounts.sources === 1 ? "" : "s"}
          </Field>
          <Link href={`${base}?tab=evidence-register`}>
            <Button type="button" variant="secondary">
              Open evidence register
            </Button>
          </Link>
        </Card>
      </div>

      {locked.length ? (
        <ExportApprovalNotice
          title="Drafts are not approved exports"
          description={`${locked.map((k) => `The ${k.toUpperCase()} is ${state(k).toLowerCase()}`).join(". ")}. Downloads stay locked until independent review approves them.`}
        />
      ) : null}
    </section>
  );
}
