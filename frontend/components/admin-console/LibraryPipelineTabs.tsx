"use client";

import { ArrowLeft, ArrowRight } from "lucide-react";
import Link from "next/link";
import { type ReactNode, useState } from "react";

import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Field } from "@/components/workbench/PageFrame";
import { cn } from "@/lib/utils";
import type {
  LibraryCheckRow,
  LibraryExtractionDetail,
  LibraryField,
  LibraryIndexValidationDetail,
  LibraryNotice,
  LibraryQualityGatesDetail,
  LibraryReleaseDetail,
} from "@/types/api";

const CHUNK_PAGE_SIZE = 4;

const CALLOUT_CLASS = {
  neutral: "bg-[var(--surface-muted)] text-[var(--text-default)]",
  warning: "border border-[#F3E2C0] bg-[#FCF3E2] text-[#8C5B12]",
  success: "border border-[#D5E8C2] bg-[#EFF6E6] text-[#356B12]",
};

/** A flat notice inside a panel: bold title over a one-line explanation. */
export function Callout({ tone, notice }: { tone: keyof typeof CALLOUT_CLASS; notice: LibraryNotice }) {
  return (
    <div className={cn("rounded-md px-3 py-2.5", CALLOUT_CLASS[tone])} role={tone === "warning" ? "status" : undefined}>
      <p className="text-xs font-semibold">{notice.title}</p>
      <p className={cn("mt-0.5 text-xs leading-5", tone === "neutral" && "text-[var(--text-muted)]")}>{notice.description}</p>
    </div>
  );
}

/**
 * The bordered checklist used across the pipeline tabs. `activeId` marks the highlighted row;
 * with `onSelect` the rows become buttons.
 */
export function CheckList({
  heading,
  rows,
  activeId,
  onSelect,
  label,
}: {
  heading: string;
  rows: LibraryCheckRow[];
  activeId?: string;
  onSelect?: (id: string) => void;
  label: string;
}) {
  return (
    <div className="rounded-md border border-[var(--surface-border)]">
      <p className="border-b border-[var(--surface-border)] px-4 py-2.5 text-xs font-semibold text-[var(--text-default)]">{heading}</p>
      <ul aria-label={label} className="px-4 py-2">
        {rows.map((row) => {
          const active = row.id === activeId;
          const body = (
            <>
              <span className={cn("block text-sm font-semibold", active ? "text-[var(--accent-green-dark)]" : "text-[var(--text-default)]")}>
                {row.label}
              </span>
              <span className="mt-0.5 flex flex-wrap items-center gap-x-2 text-xs text-[var(--text-muted)]">
                <span className={row.tone === "warn" ? "text-[#8C5B12]" : undefined}>{row.result}</span>
                <span aria-hidden>·</span>
                <span className={row.tone === "warn" ? "text-[#8C5B12]" : undefined}>{row.detail}</span>
              </span>
            </>
          );
          return (
            <li key={row.id} className="py-2">
              {onSelect ? (
                <button
                  type="button"
                  aria-pressed={active}
                  onClick={() => onSelect(row.id)}
                  className="-mx-2 block w-[calc(100%+1rem)] rounded px-2 py-1 text-left hover:bg-[var(--surface-muted)] focus-visible:outline-2 focus-visible:outline-[var(--coral-black)]"
                >
                  {body}
                </button>
              ) : (
                <div className="py-1">{body}</div>
              )}
            </li>
          );
        })}
      </ul>
    </div>
  );
}

function Panel({ title, aside, children, className }: { title: string; aside?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <Card className={cn("h-fit space-y-4 p-5", className)}>
      <div className="flex flex-wrap items-baseline gap-3">
        <h2 className="text-base font-semibold text-[var(--text-default)]">{title}</h2>
        {aside ? <span className="text-xs text-[var(--text-muted)]">{aside}</span> : null}
      </div>
      {children}
    </Card>
  );
}

function Fields({ fields }: { fields: LibraryField[] }) {
  return (
    <div className="space-y-4">
      {fields.map((field) => (
        <Field key={field.label} label={field.label}>
          {field.value}
        </Field>
      ))}
    </div>
  );
}

const TWO_COLUMN = "grid gap-4 lg:grid-cols-[minmax(0,1fr)_340px]";

export function ExtractChunkTab({ extraction, onContinue }: { extraction: LibraryExtractionDetail; onContinue: () => void }) {
  const { chunks } = extraction;
  const [page, setPage] = useState(0);
  const [activeId, setActiveId] = useState(chunks[0]?.id ?? "");
  const pageCount = Math.max(1, Math.ceil(chunks.length / CHUNK_PAGE_SIZE));
  const visible = chunks.slice(page * CHUNK_PAGE_SIZE, (page + 1) * CHUNK_PAGE_SIZE);
  const active = chunks.find((chunk) => chunk.id === activeId) ?? chunks[0];

  function turnPage(next: number) {
    setPage(next);
    setActiveId(chunks[next * CHUNK_PAGE_SIZE]?.id ?? activeId);
  }

  return (
    <div className={TWO_COLUMN}>
      <Panel title="Extracted chunk inventory">
        {extraction.error ? <Callout tone="warning" notice={extraction.error} /> : null}
        <CheckList
          heading="Chunk / page / Section / Tokens / Quality"
          label="Extracted chunks"
          rows={visible.map((chunk) => ({
            id: chunk.id,
            label: chunk.page ? `${chunk.code} · p.${chunk.page}` : chunk.code,
            result: `${chunk.section.replace(/^§[\d.]+\s*/, "") || "Untitled section"} · ${chunk.tokens}`,
            detail: chunk.quality,
            tone: chunk.tone,
          }))}
          activeId={active?.id}
          onSelect={setActiveId}
        />
        <div className="flex flex-wrap items-center gap-2">
          {page > 0 ? (
            <Button type="button" variant="secondary" className="flex items-center gap-1.5 border px-3 py-1.5 text-xs" onClick={() => turnPage(page - 1)}>
              <ArrowLeft size={14} aria-hidden />
              Previous chunks
            </Button>
          ) : null}
          {page < pageCount - 1 ? (
            <Button type="button" variant="secondary" className="flex items-center gap-1.5 border px-3 py-1.5 text-xs" onClick={() => turnPage(page + 1)}>
              Next chunks
              <ArrowRight size={14} aria-hidden />
            </Button>
          ) : null}
          <span className="ml-auto text-xs text-[var(--text-muted)]">
            {chunks.length === 0 ? "No chunks extracted" : <>Showing {page * CHUNK_PAGE_SIZE + 1}–{page * CHUNK_PAGE_SIZE + visible.length}</>} of {chunks.length} chunks
          </span>
        </div>
      </Panel>

      <Panel title="Chunk inspection">
        {active ? (
          <>
            <Field label="Chunk / source locator">
              {[active.code, active.page ? `Page ${active.page}` : null, active.section].filter(Boolean).join(" · ")}
            </Field>
            <div>
              <p className="text-sm font-semibold text-[var(--text-default)]">Extracted passage</p>
              <p className="text-2xs text-[var(--text-muted)]">{active.passageMeta}</p>
              <p className="mt-1 text-sm leading-6 text-[var(--text-default)]">{active.passage}</p>
            </div>
            <Field label="Source hash">{extraction.sourceHash}</Field>
          </>
        ) : null}
        <Callout tone="neutral" notice={extraction.provenance} />
        <Button type="button" onClick={onContinue}>
          Continue to index validation
        </Button>
      </Panel>
    </div>
  );
}

export function IndexValidateTab({ validation, onContinue }: { validation: LibraryIndexValidationDetail; onContinue: () => void }) {
  return (
    <div className="space-y-4">
      <div className={TWO_COLUMN}>
        <Panel title="Validation results" aside={validation.summary}>
          <CheckList
            heading="Validation / Result / Evidence"
            label="Index validation results"
            rows={validation.checks}
            activeId={validation.checks[0]?.id}
          />
          <Button type="button" onClick={onContinue}>
            Continue to quality review
          </Button>
        </Panel>
        <Panel title="Index inspection">
          <Fields fields={validation.inspection} />
          {validation.warning ? <Callout tone="warning" notice={validation.warning} /> : null}
        </Panel>
      </div>
      <Panel title="Sample retrieval check">
        <CheckList
          heading="Query / Top passage / Result"
          label="Sample retrieval queries"
          rows={validation.retrievalChecks}
          activeId={validation.retrievalChecks[0]?.id}
        />
      </Panel>
    </div>
  );
}

export function QualityGatesTab({
  quality,
  correctionSent,
  onRequestCorrection,
  onUploadCorrection,
  publishAction,
}: {
  quality: LibraryQualityGatesDetail;
  correctionSent: string | null;
  onRequestCorrection: () => void;
  /** Uploaded sources only: attach a corrected file to this practice. */
  onUploadCorrection?: () => void;
  publishAction: ReactNode;
}) {
  const open = quality.openCorrection;
  return (
    <div className={TWO_COLUMN}>
      <Panel title="Source quality gates">
        <CheckList heading="Gate / Result / Action" label="Source quality gates" rows={quality.gates} activeId={quality.gates[0]?.id} />
        {quality.blocker ? <Callout tone="warning" notice={quality.blocker} /> : null}
        {correctionSent || open ? (
          <Callout
            tone="success"
            notice={{
              title: `Correction request sent · ${correctionSent ?? open?.id}`,
              description: `${open?.assignee || quality.correction.assignee} has been notified. The candidate stays unpublished until a corrected source passes the gates.`,
            }}
          />
        ) : null}
        <div className="flex flex-wrap gap-2">
          {quality.blocker || !onUploadCorrection ? (
            <Button type="button" onClick={onRequestCorrection}>
              {correctionSent || open ? "Update correction request" : "Request correction"}
            </Button>
          ) : null}
          {onUploadCorrection ? (
            <Button type="button" variant={quality.blocker ? "secondary" : undefined} onClick={onUploadCorrection}>
              Upload corrected source
            </Button>
          ) : null}
        </div>
      </Panel>
      <Panel title="Metadata & source review">
        <Fields fields={quality.metadata} />
        {publishAction}
      </Panel>
    </div>
  );
}

export function ApprovePublishTab({ release, publishAction }: { release: LibraryReleaseDetail; publishAction?: ReactNode }) {
  // The sample walkthrough has no `published` flag: it illustrates the released state.
  const published = release.published ?? true;
  return (
    <div className={TWO_COLUMN}>
      <Panel title="Corrected candidate & release gates">
        <CheckList heading="Gate / Result / Record" label="Release gates" rows={release.gates} activeId={release.gates[0]?.id} />
        <Callout tone={published ? "success" : "neutral"} notice={release.notice} />
        {published ? (
        <Link
          href={`/library?practice=${encodeURIComponent(release.practiceId)}`}
          className="inline-block rounded-md bg-[var(--accent-green)] px-4 py-2 text-sm font-medium !text-white no-underline transition hover:bg-[var(--accent-green-dark)] hover:no-underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--coral-black)]"
        >
          View published practice
        </Link>
        ) : (
          publishAction
        )}
      </Panel>
      <Panel title="Release record">
        <Fields fields={release.record} />
      </Panel>
    </div>
  );
}
