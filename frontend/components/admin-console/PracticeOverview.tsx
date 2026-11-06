"use client";

import { ChevronRight, FilePlus2, FileText } from "lucide-react";
import { type FormEvent, type ReactNode, useState } from "react";

import { LibraryBadge } from "@/components/admin-console/LibraryStatus";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { DataTable } from "@/components/ui/DataTable";
import { EmptyState } from "@/components/ui/EmptyState";
import { Input } from "@/components/ui/Input";
import { Select } from "@/components/ui/Select";
import { Textarea } from "@/components/ui/Textarea";
import { CLASSIFICATION, MATURITY, type PracticeDetails, TAXONOMY } from "@/lib/libraryPractices";
import { cn } from "@/lib/utils";
import type { LibrarySource } from "@/types/api";

const FIELD_LABEL = "grid gap-1.5 text-sm text-[var(--text-default)]";
const FIELD_CAPTION = "text-2xs font-semibold uppercase tracking-wide text-[var(--text-muted)]";
// Text fields at the height of the dropdowns beside them.
const FIELD_INPUT = "min-h-11";

function FormSection({ title, description, children }: { title: string; description: string; children: ReactNode }) {
  return (
    <section className="space-y-4 border-b border-[var(--surface-border)] pb-6 last:border-b-0 last:pb-0">
      <div>
        <h2 className="text-sm font-semibold text-[var(--text-default)]">{title}</h2>
        <p className="mt-0.5 text-xs text-[var(--text-muted)]">{description}</p>
      </div>
      {children}
    </section>
  );
}

const NEXT_STEPS = [
  { title: "Create the practice", detail: "Saved with these details, as a draft." },
  { title: "Upload sources", detail: "Add its documents from the practice page." },
  { title: "Review each source", detail: "Extraction, index validation and quality review." },
  { title: "Approve & publish", detail: "Only then is it available to users." },
];

/** Create practice: the details a practice is created with, before any source is uploaded. */
export function PracticeDetailsForm({
  onSubmit,
  onCancel,
  initial,
  submitting = false,
}: {
  onSubmit: (details: PracticeDetails) => void;
  onCancel: () => void;
  initial: PracticeDetails;
  /** While the practice is being created: the buttons are disabled. */
  submitting?: boolean;
}) {
  const [details, setDetails] = useState(initial);
  const set = (key: keyof PracticeDetails) => (value: string) => setDetails((current) => ({ ...current, [key]: value }));

  function submit(event: FormEvent) {
    event.preventDefault();
    onSubmit({ ...details, title: details.title.trim(), owner: details.owner.trim(), rights: details.rights.trim(), description: details.description.trim() });
  }

  return (
    <form onSubmit={submit} aria-label="Practice details" className="grid grid-cols-1 items-start gap-5 lg:grid-cols-[minmax(0,1fr)_340px]">
      <Card className="space-y-6">
        <FormSection title="Basic details" description="How the practice is named and described in the library.">
          <label className={FIELD_LABEL}>
            <span className={FIELD_CAPTION}>Practice title *</span>
            <Input
              required
              minLength={2}
              maxLength={200}
              value={details.title}
              onChange={(e) => set("title")(e.target.value)}
              placeholder="e.g. Vendor onboarding playbook"
              className={FIELD_INPUT}
            />
          </label>
          <label className={FIELD_LABEL}>
            <span className={FIELD_CAPTION}>Description</span>
            <Textarea
              rows={4}
              maxLength={2000}
              value={details.description}
              onChange={(e) => set("description")(e.target.value)}
              placeholder="What the practice covers and when to use it"
              className="rounded-md"
            />
          </label>
        </FormSection>

        <FormSection title="Classification" description="Where the practice sits in the library and who may see it.">
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <label className={FIELD_LABEL}>
              <span className={FIELD_CAPTION}>Taxonomy</span>
              <Select value={details.taxonomy} onChange={(e) => set("taxonomy")(e.target.value)}>
                {TAXONOMY.map((item) => (
                  <option key={item}>{item}</option>
                ))}
              </Select>
            </label>
            <label className={FIELD_LABEL}>
              <span className={FIELD_CAPTION}>Maturity</span>
              <Select value={details.maturity} onChange={(e) => set("maturity")(e.target.value)}>
                {MATURITY.map((item) => (
                  <option key={item}>{item}</option>
                ))}
              </Select>
            </label>
            <label className={FIELD_LABEL}>
              <span className={FIELD_CAPTION}>Classification</span>
              <Select value={details.classification} onChange={(e) => set("classification")(e.target.value)}>
                {CLASSIFICATION.map((item) => (
                  <option key={item}>{item}</option>
                ))}
              </Select>
            </label>
            <label className={FIELD_LABEL}>
              <span className={FIELD_CAPTION}>Version</span>
              <Input value={details.version} onChange={(e) => set("version")(e.target.value)} placeholder="v1.0" className={FIELD_INPUT} />
            </label>
          </div>
        </FormSection>

        <FormSection title="Ownership & rights" description="Who answers for the practice, and on what terms its sources may be used.">
          <div className="grid gap-4 sm:grid-cols-2">
            <label className={FIELD_LABEL}>
              <span className={FIELD_CAPTION}>Practice owner *</span>
              <Input
                required
                minLength={2}
                value={details.owner}
                onChange={(e) => set("owner")(e.target.value)}
                placeholder="Name or team"
                className={FIELD_INPUT}
              />
            </label>
            <label className={FIELD_LABEL}>
              <span className={FIELD_CAPTION}>Source attribution and rights *</span>
              <Input required minLength={3} value={details.rights} onChange={(e) => set("rights")(e.target.value)} className={FIELD_INPUT} />
            </label>
          </div>
        </FormSection>
      </Card>

      <Card className="space-y-5 lg:sticky lg:top-4">
        <div>
          <h2 className="text-sm font-semibold text-[var(--text-default)]">What happens next</h2>
          <p className="mt-0.5 text-xs text-[var(--text-muted)]">Creating the practice does not publish anything.</p>
        </div>
        <ol className="space-y-3">
          {NEXT_STEPS.map((step, index) => (
            <li key={step.title} className="flex gap-3">
              <span
                className={cn(
                  "flex h-6 w-6 shrink-0 items-center justify-center rounded-full border text-2xs font-semibold",
                  index === 0
                    ? "border-[var(--accent-green)] bg-[#EFF6E6] text-[var(--accent-green-dark)]"
                    : "border-[var(--surface-border-strong)] bg-white text-[var(--text-muted)]"
                )}
              >
                {index + 1}
              </span>
              <span>
                <span className="block text-xs font-semibold text-[var(--text-default)]">{step.title}</span>
                <span className="block text-2xs text-[var(--text-muted)]">{step.detail}</span>
              </span>
            </li>
          ))}
        </ol>
        <p className="text-2xs text-[var(--text-muted)]">Fields marked * are required.</p>
        <div className="flex flex-col gap-2 border-t border-[var(--surface-border)] pt-4">
          <Button type="submit" className="w-full" disabled={submitting}>
            {submitting ? "Creating…" : "Create practice"}
          </Button>
          <Button type="button" variant="secondary" className="w-full" disabled={submitting} onClick={onCancel}>
            Cancel
          </Button>
        </div>
      </Card>
    </form>
  );
}

function Detail({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="min-w-0">
      <p className="text-2xs font-semibold uppercase tracking-wide text-[var(--text-muted)]">{label}</p>
      <div className="mt-1 break-words text-sm text-[var(--text-default)]">{children || "—"}</div>
    </div>
  );
}

/** The details a practice was created with. */
export function PracticeDetailsCard({ details, status, footer }: { details: Partial<PracticeDetails>; status: string; footer?: ReactNode }) {
  return (
    <Card className="space-y-4">
      <div className="flex items-center justify-between gap-3">
        <h2 className="text-sm font-semibold text-[var(--text-default)]">Practice details</h2>
        <LibraryBadge>{status}</LibraryBadge>
      </div>
      {details.description ? <p className="text-sm leading-6 text-[var(--text-default)]">{details.description}</p> : null}
      <div className="grid gap-4 sm:grid-cols-3">
        <Detail label="Taxonomy">{details.taxonomy}</Detail>
        <Detail label="Maturity">{details.maturity}</Detail>
        <Detail label="Version">{details.version}</Detail>
        <Detail label="Practice owner">{details.owner}</Detail>
        <Detail label="Classification">{details.classification}</Detail>
        <Detail label="Source attribution and rights">{details.rights}</Detail>
      </div>
      {footer ? <div className="flex flex-wrap items-start gap-2 border-t border-[var(--surface-border)] pt-4">{footer}</div> : null}
    </Card>
  );
}

const formatTime = (iso: string) => {
  const date = new Date(iso);
  return Number.isNaN(date.getTime())
    ? iso
    : date.toLocaleString(undefined, { day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" });
};

const formatSize = (bytes: number | null) =>
  !bytes ? "—" : bytes < 1024 * 1024 ? `${Math.max(1, Math.round(bytes / 1024))} KB` : `${(bytes / 1024 / 1024).toFixed(1)} MB`;

/** The practice's sources; each opens its pipeline, takes a new version, and lists its versions. */
export function PracticeSourcesPanel({
  sources,
  statusLabel,
  onOpen,
  onNewVersion,
  action,
}: {
  sources: LibrarySource[];
  statusLabel: (status: string) => string;
  onOpen: (sourceId: string) => void;
  onNewVersion: (sourceId: string) => void;
  action?: ReactNode;
}) {
  const [expanded, setExpanded] = useState<string | null>(sources.length === 1 ? sources[0].id : null);
  return (
    <Card className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold text-[var(--text-default)]">
            Sources <span className="font-normal text-[var(--text-muted)]">· {sources.length}</span>
          </h2>
          <p className="text-xs text-[var(--text-muted)]">Each source goes through extraction, validation, quality review and publication.</p>
        </div>
        {action}
      </div>
      {sources.length === 0 ? (
        <EmptyState title="No sources yet" description="Upload a source to start extraction, validation and review for this practice." />
      ) : (
        <ul className="divide-y divide-[var(--surface-border)] rounded-md border border-[var(--surface-border)]" aria-label="Sources">
          {sources.map((source) => {
            const latest = source.versions[0];
            const open = expanded === source.id;
            return (
              <li key={source.id}>
                <div className="flex flex-wrap items-center gap-3 px-4 py-3">
                  <Button
                    type="button"
                    variant="ghost"
                    aria-expanded={open}
                    aria-label={`${open ? "Hide" : "Show"} versions of ${source.name}`}
                    className="p-1"
                    onClick={() => setExpanded(open ? null : source.id)}
                  >
                    <ChevronRight size={16} className={cn("transition-transform", open && "rotate-90")} aria-hidden />
                  </Button>
                  <FileText size={16} className="text-[var(--text-muted)]" aria-hidden />
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-semibold text-[var(--text-default)]" title={source.name}>
                      {source.name}
                    </p>
                    <p className="text-xs text-[var(--text-muted)]">
                      {source.id} · {source.versions.length} version{source.versions.length === 1 ? "" : "s"}
                      {latest ? ` · Latest ${formatTime(latest.uploadedAt)}` : ""}
                    </p>
                  </div>
                  {latest ? <LibraryBadge>{statusLabel(latest.status)}</LibraryBadge> : null}
                  <Button type="button" variant="secondary" className="flex items-center gap-1.5 px-3 py-1.5 text-xs" onClick={() => onNewVersion(source.id)}>
                    <FilePlus2 size={14} aria-hidden />
                    New version
                  </Button>
                  <Button type="button" className="px-3 py-1.5 text-xs" onClick={() => onOpen(source.id)}>
                    Open pipeline
                  </Button>
                </div>
                {open ? (
                  <DataTable
                    bare
                    paginate={source.versions.length > 10}
                    label={`Versions of ${source.name}`}
                    itemName="versions"
                    rows={source.versions}
                    rowKey={(version) => version.jobId}
                    minWidth="min-w-[560px]"
                    columns={[
                      {
                        key: "version",
                        header: "Version",
                        sortValue: (version) => version.number,
                        cell: (version) => (
                          <span className="whitespace-nowrap font-semibold text-[var(--text-default)]">
                            Version {version.number}
                            {version.number === latest?.number ? <span className="ml-1.5 font-normal text-[var(--text-muted)]">(latest)</span> : null}
                          </span>
                        ),
                      },
                      {
                        key: "file",
                        header: "File",
                        sortValue: (version) => version.filename,
                        cell: (version) => (
                          <span className="block max-w-[260px] truncate" title={version.filename}>
                            {version.filename}
                          </span>
                        ),
                      },
                      {
                        key: "uploaded",
                        header: "Uploaded",
                        sortValue: (version) => version.uploadedAt,
                        cell: (version) => <span className="whitespace-nowrap text-[var(--text-muted)]">{formatTime(version.uploadedAt)}</span>,
                      },
                      { key: "size", header: "Size", hideBelow: "md", sortValue: (version) => version.sizeBytes ?? 0, cell: (version) => <span className="text-[var(--text-muted)]">{formatSize(version.sizeBytes)}</span> },
                      { key: "status", header: "Status", sortValue: (version) => version.status, cell: (version) => <LibraryBadge dot>{statusLabel(version.status)}</LibraryBadge> },
                    ]}
                  />
                ) : null}
              </li>
            );
          })}
        </ul>
      )}
    </Card>
  );
}
