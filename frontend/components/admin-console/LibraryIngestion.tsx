"use client";

import { Trash2 } from "lucide-react";
import { useState } from "react";

import { LibraryBadge, type LibraryBadgeTone } from "@/components/admin-console/LibraryStatus";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { ErrorNote } from "@/components/workbench/PageFrame";
import {
  type IngestionJobStatus,
  useDeletePractice,
  useIngestionJobDetails,
  useIngestionJobStatus,
  useLibraryIngestionJobs,
} from "@/hooks/useAdminConsole";
import { cn } from "@/lib/utils";

// Pipeline stage ids (src/workers/pipeline.py) as the admin reads them.
const STAGE_LABEL: Record<string, string> = {
  queued: "Queued",
  intake: "Intake",
  uploading: "Storing source",
  parsing: "Parsing",
  chunking: "Chunking",
  embedding: "Embedding",
  library_validation: "Library validation",
  extracting_facts: "Extracting facts",
  generating_wiki: "Generating wiki",
  deduplicating: "Deduplicating",
  indexing_wiki: "Indexing wiki",
  completed: "Completed",
  failed: "Failed",
  deleted: "Deleted",
};

const stageLabel = (stage: string) => STAGE_LABEL[stage] ?? stage.replace(/_/g, " ");

function statusTone(job: IngestionJobStatus): LibraryBadgeTone {
  if (job.status === "completed") return "success";
  if (job.status === "failed") return "error";
  return job.is_terminal ? "neutral" : "warning";
}

const countsLine = ({ counts }: IngestionJobStatus) =>
  `${counts.chunks} chunks · ${counts.embeddings} embeddings · ${counts.facts} facts · ${counts.wiki_pages} wiki pages`;

function ProgressBar({ job }: { job: IngestionJobStatus }) {
  return (
    <div
      role="progressbar"
      aria-label={`${job.filename} progress`}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={job.progress_percent}
      className="h-1.5 w-full overflow-hidden rounded-full bg-[var(--surface-muted)]"
    >
      <div
        className={cn(
          "h-full rounded-full transition-[width] duration-500",
          job.status === "failed" ? "bg-[var(--error)]" : "bg-[var(--accent-green)]",
        )}
        style={{ width: `${job.progress_percent}%` }}
      />
    </div>
  );
}

/** One upload's live progress: polled every 3 seconds until the pipeline finishes or fails. */
function UploadProgressRow({ jobId, onOpenPractice }: { jobId: string; onOpenPractice?: (practiceId: string) => void }) {
  const { data: job, error } = useIngestionJobStatus(jobId);
  if (!job) return error ? <ErrorNote error={error} /> : <p className="text-xs text-[var(--text-muted)]">Waiting for {jobId}…</p>;

  const stage = job.status === "failed" && job.failed_stage ? `Failed at ${stageLabel(job.failed_stage)}` : stageLabel(job.status);
  return (
    <li className="space-y-1.5">
      <div className="flex items-center justify-between gap-3">
        <span className="truncate text-xs font-semibold text-[var(--text-default)]">{job.filename}</span>
        <span className="flex shrink-0 items-center gap-2">
          <span className="text-2xs text-[var(--text-muted)]">{job.progress_percent}%</span>
          <LibraryBadge tone={statusTone(job)}>{stage}</LibraryBadge>
        </span>
      </div>
      <ProgressBar job={job} />
      <div className="flex flex-wrap items-center justify-between gap-2 text-2xs text-[var(--text-muted)]">
        <span>{countsLine(job)}</span>
        {job.practice_id && onOpenPractice ? (
          <button
            type="button"
            className="font-semibold text-[var(--accent-green-dark)] underline underline-offset-2"
            onClick={() => onOpenPractice(job.practice_id as string)}
          >
            Open {job.practice_id.toUpperCase()}
          </button>
        ) : null}
      </div>
      {job.error_message ? (
        <p role="alert" className="text-2xs text-[var(--error)]">
          {job.error_message}
        </p>
      ) : null}
    </li>
  );
}

/** Progress of the files from the latest upload, shown under the Upload sources button. */
export function UploadProgressPanel({
  jobIds,
  onOpenPractice,
  onDismiss,
}: {
  jobIds: string[];
  onOpenPractice?: (practiceId: string) => void;
  onDismiss?: () => void;
}) {
  if (jobIds.length === 0) return null;
  return (
    <Card className="space-y-3" aria-live="polite">
      <div className="flex items-center justify-between gap-3">
        <h2 className="text-sm font-semibold text-[var(--text-default)]">Upload progress</h2>
        {onDismiss ? (
          <Button type="button" variant="ghost" className="px-2 py-1 text-2xs" onClick={onDismiss}>
            Dismiss
          </Button>
        ) : null}
      </div>
      <ul className="space-y-4">
        {jobIds.map((id) => (
          <UploadProgressRow key={id} jobId={id} onOpenPractice={onOpenPractice} />
        ))}
      </ul>
    </Card>
  );
}

const formatTime = (iso: string) =>
  new Date(iso).toLocaleString(undefined, { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" });

/** Every Library upload with its pipeline status and counts; a row with a practice selects it. */
export function LibraryUploadsPanel({ activeId, onSelect }: { activeId: string; onSelect: (practiceId: string) => void }) {
  const jobs = useLibraryIngestionJobs();
  const rows = jobs.data ?? [];
  return (
    <Card className="space-y-3">
      <div className="flex items-center justify-between gap-3">
        <h2 className="text-sm font-semibold text-[var(--text-default)]">Uploads</h2>
        <span className="text-2xs text-[var(--text-muted)]">{jobs.data ? `${rows.length} documents` : null}</span>
      </div>
      <ErrorNote error={jobs.error} />
      {jobs.isPending ? (
        <p className="text-xs text-[var(--text-muted)]">Loading uploads…</p>
      ) : rows.length === 0 && !jobs.error ? (
        <p className="text-xs text-[var(--text-muted)]">No sources have been uploaded yet.</p>
      ) : (
        <div className="overflow-x-auto rounded-md border border-[var(--surface-border)]">
          <table className="w-full min-w-[560px] text-left text-xs">
            <thead>
              <tr className="border-b border-[var(--surface-border)] bg-[var(--surface-muted)] text-[var(--text-muted)]">
                <th className="px-3 py-2 font-medium">File</th>
                <th className="px-3 py-2 font-medium">Practice</th>
                <th className="px-3 py-2 font-medium">Status</th>
                <th className="px-3 py-2 font-medium">Counts</th>
                <th className="px-3 py-2 font-medium">Uploaded</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((job) => {
                const practice = job.practice_id;
                const active = Boolean(practice) && practice === activeId;
                return (
                  <tr
                    key={job.job_id}
                    onClick={practice ? () => onSelect(practice) : undefined}
                    aria-selected={active}
                    className={cn(
                      "border-b border-[var(--surface-border)] align-top last:border-b-0",
                      practice && "cursor-pointer",
                      active ? "bg-[#EFF6E6]" : practice && "hover:bg-[var(--surface-muted)]",
                    )}
                  >
                    <td className="max-w-[220px] px-3 py-2">
                      <span className="block truncate font-medium text-[var(--text-default)]" title={job.filename}>
                        {job.filename}
                      </span>
                      {job.error_message ? (
                        <span className="block truncate text-2xs text-[var(--error)]" title={job.error_message}>
                          {job.error_message}
                        </span>
                      ) : null}
                    </td>
                    <td className="px-3 py-2 text-[var(--text-default)]">{practice ? practice.toUpperCase() : "—"}</td>
                    <td className="space-y-1 px-3 py-2">
                      <LibraryBadge tone={statusTone(job)}>{stageLabel(job.status)}</LibraryBadge>
                      {!job.is_terminal ? <ProgressBar job={job} /> : null}
                    </td>
                    <td className="px-3 py-2 text-[var(--text-muted)]">
                      {job.counts.chunks} chunks · {job.counts.embeddings} vectors
                      <br />
                      {job.counts.facts} facts · {job.counts.wiki_pages} wiki
                    </td>
                    <td className="whitespace-nowrap px-3 py-2 text-[var(--text-muted)]">{formatTime(job.created_at)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
}

function Stat({ label, value }: { label: string; value: string | number | null | undefined }) {
  return (
    <div>
      <p className="text-2xs font-medium uppercase tracking-wide text-[var(--text-muted)]">{label}</p>
      <p className="mt-0.5 text-xs font-semibold text-[var(--text-default)]">{value ?? "—"}</p>
    </div>
  );
}

/** What the pipeline stored for one file: the source object, chunks, vectors, facts and wiki pages. */
export function StoredDataPanel({ jobId }: { jobId: string }) {
  const details = useIngestionJobDetails(jobId);
  const data = details.data;
  return (
    <Card className="space-y-4 p-5">
      <div className="flex flex-wrap items-baseline gap-3">
        <h2 className="text-base font-semibold text-[var(--text-default)]">Stored by the pipeline</h2>
        {data ? (
          <span className="text-xs text-[var(--text-muted)]">
            {data.job.filename} · {stageLabel(data.job.status)}
          </span>
        ) : null}
      </div>
      <ErrorNote error={details.error} />
      {details.isPending ? <p className="text-xs text-[var(--text-muted)]">Loading stored data…</p> : null}
      {data && !data.postgres ? (
        <p className="text-xs text-[var(--text-muted)]">Nothing has been stored for this file yet.</p>
      ) : null}
      {data?.postgres ? (
        <>
          <div className="grid gap-4 sm:grid-cols-4">
            <Stat label="Pages" value={data.postgres.page_count} />
            <Stat
              label="Chunks"
              value={`${data.postgres.chunk_count}${data.postgres.reused_chunk_count ? ` (${data.postgres.reused_chunk_count} reused)` : ""}`}
            />
            <Stat label="Embeddings" value={data.qdrant?.points_for_document ?? data.job.counts.embeddings} />
            <Stat label="Facts · wiki pages" value={`${data.knowledge?.fact_count ?? 0} · ${data.knowledge?.wiki_pages.length ?? 0}`} />
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <Stat label="Source object" value={data.seaweedfs ? `${data.seaweedfs.bucket}/${data.seaweedfs.key}` : null} />
            <Stat label="Vector collection" value={data.qdrant?.collection} />
          </div>
          {data.seaweedfs?.error || data.qdrant?.error ? (
            <p role="status" className="text-2xs text-[#8C5B12]">
              {[data.seaweedfs?.error && `Storage: ${data.seaweedfs.error}`, data.qdrant?.error && `Vectors: ${data.qdrant.error}`]
                .filter(Boolean)
                .join(" · ")}
            </p>
          ) : null}

          {data.postgres.chunks.length > 0 ? (
            <div className="rounded-md border border-[var(--surface-border)]">
              <p className="border-b border-[var(--surface-border)] px-4 py-2.5 text-xs font-semibold text-[var(--text-default)]">
                Stored chunks (first {data.postgres.chunks.length} of {data.postgres.chunk_count})
              </p>
              <ul className="max-h-72 divide-y divide-[var(--surface-border)] overflow-y-auto" aria-label="Stored chunks">
                {data.postgres.chunks.map((chunk) => (
                  <li key={chunk.id} className="px-4 py-2">
                    <p className="text-2xs text-[var(--text-muted)]">
                      #{chunk.chunk_number}
                      {chunk.page_number ? ` · p.${chunk.page_number}` : ""} · {chunk.source_type} · {chunk.characters} chars
                      {chunk.reused ? " · reused" : ""}
                    </p>
                    <p className="text-xs leading-5 text-[var(--text-default)]">{chunk.preview}</p>
                  </li>
                ))}
              </ul>
            </div>
          ) : null}

          {data.knowledge && (data.knowledge.facts.length > 0 || data.knowledge.wiki_pages.length > 0) ? (
            <div className="grid gap-4 lg:grid-cols-2">
              <div>
                <p className="text-xs font-semibold text-[var(--text-default)]">Facts</p>
                <ul className="mt-1 space-y-1 text-xs text-[var(--text-default)]">
                  {data.knowledge.facts.map((fact, i) => (
                    <li key={`${fact.type}-${fact.name}-${i}`}>
                      <span className="text-[var(--text-muted)]">{fact.type}</span> · {fact.name}
                    </li>
                  ))}
                </ul>
              </div>
              <div>
                <p className="text-xs font-semibold text-[var(--text-default)]">Wiki pages</p>
                <ul className="mt-1 space-y-1 text-xs text-[var(--text-default)]">
                  {data.knowledge.wiki_pages.map((page) => (
                    <li key={page.id}>
                      {page.entity_name} <span className="text-[var(--text-muted)]">· {page.entity_type}</span>
                      {page.merge_count ? <span className="text-[var(--text-muted)]"> · merged {page.merge_count}×</span> : null}
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          ) : null}
        </>
      ) : null}
    </Card>
  );
}

/** Delete a practice and all of its pipeline data, after an inline confirmation. */
export function DeletePracticeButton({
  practiceId,
  className,
  onDeleted,
}: {
  practiceId: string;
  className?: string;
  onDeleted: (message: string) => void;
}) {
  const remove = useDeletePractice();
  const [confirming, setConfirming] = useState(false);
  const code = practiceId.toUpperCase();

  if (!confirming) {
    return (
      <Button
        type="button"
        variant="secondary"
        className={cn("flex items-center gap-1.5 whitespace-nowrap border border-[var(--surface-border-strong)] text-[var(--error)]", className)}
        onClick={() => setConfirming(true)}
      >
        <Trash2 size={14} aria-hidden />
        Delete
      </Button>
    );
  }

  async function confirm() {
    const result = await remove.mutateAsync(practiceId);
    setConfirming(false);
    onDeleted(`${result.deleted.toUpperCase()} deleted · ${result.sources_removed} source(s) and their pipeline data removed.`);
  }

  return (
    <div role="alertdialog" aria-label={`Delete ${code}`} className="w-full space-y-2 rounded-md border border-[#EFC9C3] bg-[#FBEFEB] p-3">
      <p className="text-sm font-semibold text-[#A53E37]">Delete {code}?</p>
      <p className="text-xs text-[var(--text-default)]">
        This removes every uploaded version, its review and comments, and its stored sources, chunks, vectors, facts and wiki
        contributions. It cannot be undone.
      </p>
      <ErrorNote error={remove.error} />
      <div className="flex gap-2">
        <Button type="button" className="bg-[#A53E37] text-sm hover:bg-[#8A322C]" disabled={remove.isPending} onClick={() => void confirm()}>
          {remove.isPending ? "Deleting…" : "Delete practice"}
        </Button>
        <Button type="button" variant="secondary" className="text-sm" disabled={remove.isPending} onClick={() => setConfirming(false)}>
          Cancel
        </Button>
      </div>
    </div>
  );
}
