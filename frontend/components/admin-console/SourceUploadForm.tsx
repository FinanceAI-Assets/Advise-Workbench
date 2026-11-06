"use client";

import { Upload, X } from "lucide-react";
import { type ChangeEvent, type DragEvent, type FormEvent, useState } from "react";

import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Input } from "@/components/ui/Input";
import { Select } from "@/components/ui/Select";
import { ErrorNote } from "@/components/workbench/PageFrame";
import { type LibraryUploadJob, useLibraryUpload } from "@/hooks/useAdminConsole";
import { CLASSIFICATION } from "@/lib/libraryPractices";
import { cn } from "@/lib/utils";

// Keep in step with SUPPORTED_EXTENSIONS in src/memory/knowledge/practice_ingest.py.
const ACCEPTED_EXTENSIONS = [".pdf", ".docx", ".pptx", ".xlsx", ".md", ".txt"];
const ACCEPTED_SOURCE_TYPES = ACCEPTED_EXTENSIONS.join(",");
// Office 97-2003 formats the server cannot read; the admin is asked to re-save them.
const LEGACY_OFFICE: Record<string, string> = { ".doc": ".docx", ".ppt": ".pptx", ".xls": ".xlsx" };
const MAX_FILE_SIZE = 25 * 1024 * 1024;

// Form controls inherit the label's font (globals.css), so the caption styling sits on a span.
const FIELD_LABEL = "grid gap-1.5 text-sm text-[var(--text-default)]";
const FIELD_CAPTION = "text-2xs font-semibold uppercase tracking-wide text-[var(--text-muted)]";

const extensionOf = (name: string) => (name.includes(".") ? name.slice(name.lastIndexOf(".")).toLowerCase() : "");
const fileKey = (file: File) => `${file.name}-${file.size}-${file.lastModified}`;
const formatSize = (bytes: number) =>
  bytes < 1024 * 1024 ? `${Math.max(1, Math.round(bytes / 1024))} KB` : `${(bytes / 1024 / 1024).toFixed(1)} MB`;

/** Why a file cannot be uploaded, or null when it can. Mirrors the server's checks for a faster answer. */
function rejectionFor(file: File): string | null {
  const ext = extensionOf(file.name);
  if (LEGACY_OFFICE[ext]) return `${file.name}: the older ${ext} format cannot be read. Save it as ${LEGACY_OFFICE[ext]} and try again.`;
  if (!ACCEPTED_EXTENSIONS.includes(ext)) return `${file.name}: only PDF, Word, PowerPoint, Excel, Markdown or text files are accepted.`;
  if (file.size === 0) return `${file.name} is empty.`;
  if (file.size > MAX_FILE_SIZE) return `${file.name} exceeds the 25 MB file limit.`;
  return null;
}

/** Where the files go: new sources of a practice, or the next version of one of its sources. */
export type UploadTarget =
  | { kind: "source"; practiceId: string; owner: string; classification: string; rights: string }
  | { kind: "version"; practiceId: string; sourceId: string; sourceName: string; owner: string; classification: string; rights: string };

/** The Source upload step's form: pick or drop files, then start the pipeline. */
export function SourceUploadForm({
  target,
  maxFiles = 1,
  note,
  onUploaded,
  onCancel,
}: {
  target: UploadTarget;
  /** Files per upload: several new sources at once, or one new version. */
  maxFiles?: number;
  note?: string;
  onUploaded: (jobs: LibraryUploadJob[]) => void;
  onCancel?: () => void;
}) {
  const upload = useLibraryUpload();
  const [files, setFiles] = useState<File[]>([]);
  const [version, setVersion] = useState("");
  const [owner, setOwner] = useState(target.owner);
  const [classification, setClassification] = useState(target.classification || CLASSIFICATION[0]);
  const [rights, setRights] = useState(target.rights);
  const [error, setError] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);
  const single = maxFiles === 1;

  function selectFiles(event: ChangeEvent<HTMLInputElement>) {
    const selected = Array.from(event.target.files ?? []);
    // Clear the input so picking the same file again still fires a change.
    event.target.value = "";
    addFiles(selected);
  }

  function dropFiles(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    setDragging(false);
    if (!upload.isPending) addFiles(Array.from(event.dataTransfer.files));
  }

  /** Files from the picker or a drop: checked, then added to the list (with one file allowed, it replaces). */
  function addFiles(selected: File[]) {
    if (selected.length === 0) return;
    const rejection = selected.map(rejectionFor).find(Boolean);
    if (rejection) {
      setError(rejection);
      return;
    }
    const known = new Set(files.map(fileKey));
    const next = single ? selected : [...files, ...selected.filter((file) => !known.has(fileKey(file)))];
    if (next.length > maxFiles) {
      setError(single ? "Attach one file at a time." : `Upload up to ${maxFiles} sources at a time.`);
      return;
    }
    setError(null);
    setFiles(next);
  }

  function removeFile(key: string) {
    setFiles((current) => current.filter((file) => fileKey(file) !== key));
    setError(null);
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (files.length === 0) {
      setError("Select a PDF, Word, PowerPoint, Excel, Markdown or text file.");
      return;
    }
    const form = new FormData();
    files.forEach((file) => form.append("files", file));
    form.append("owner", owner.trim());
    form.append("classification", classification);
    form.append("rights", rights.trim());
    if (version.trim()) form.append("version", version.trim());
    form.append("practice_id", target.practiceId);
    form.append("source_id", target.kind === "version" ? target.sourceId : "new");
    try {
      const result = await upload.mutateAsync(form);
      onUploaded(result.jobs);
    } catch {
      // upload.error is shown below.
    }
  }

  const heading = target.kind === "version" ? `New version of ${target.sourceName}` : "Upload source";

  return (
    <Card>
      <form className="space-y-4" onSubmit={(event) => void submit(event)} aria-label={heading}>
        <div>
          <h2 className="text-sm font-semibold text-[var(--text-default)]">{heading}</h2>
          <p className="mt-1 text-xs text-[var(--text-muted)]">
            PDF, Word, PowerPoint, Excel, Markdown or text · {single ? "One file" : `Up to ${maxFiles} files`}, 25 MB each ·
            Text-readable sources required
          </p>
        </div>

        <fieldset disabled={upload.isPending} className="space-y-4">
          {/* Drag and drop is a pointer shortcut; the label and file input stay the keyboard path. */}
          <div
            role="presentation"
            onDragOver={(event) => {
              event.preventDefault();
              setDragging(true);
            }}
            onDragLeave={(event) => {
              // Moving onto the text inside the box also fires dragleave; only reset when leaving the box.
              if (!event.currentTarget.contains(event.relatedTarget as Node | null)) setDragging(false);
            }}
            onDrop={dropFiles}
          >
            <label
              className={cn(
                "block cursor-pointer rounded-md border border-dashed p-6 text-center transition focus-within:ring-2 focus-within:ring-[var(--accent-green)]",
                dragging
                  ? "border-[var(--accent-green)] bg-[#EFF6E6]"
                  : "border-[var(--surface-border-strong)] bg-[var(--surface-muted)] hover:border-[var(--accent-green)]"
              )}
            >
              <Upload size={20} className="mx-auto text-[var(--accent-green-dark)]" aria-hidden />
              <span className="mt-2 block text-sm font-medium text-[var(--text-default)]">
                {single ? "Drag and drop the file here, or " : "Drag and drop files here, or "}
                <span className="text-[var(--accent-green-dark)] underline underline-offset-2">browse</span>
              </span>
              <span className="mt-1 block text-xs text-[var(--text-muted)]">
                {target.kind === "version"
                  ? "The new version goes through review; the published version stays live until it is released."
                  : single
                    ? "Extraction, chunking and validation start as soon as it is uploaded."
                    : `Select up to ${maxFiles} files; each becomes a source of this practice.`}
              </span>
              <input className="sr-only" type="file" accept={ACCEPTED_SOURCE_TYPES} multiple={!single} onChange={selectFiles} />
            </label>
          </div>

          {files.length > 0 ? (
            <ul className="space-y-2" aria-label="Selected source files">
              {files.map((file) => (
                <li key={fileKey(file)} className="flex items-center justify-between gap-3 text-sm">
                  <span className="truncate font-medium text-[var(--text-default)]">{file.name}</span>
                  <span className="flex shrink-0 items-center gap-2">
                    <span className="text-xs text-[var(--success)]">Ready · {formatSize(file.size)}</span>
                    <Button type="button" variant="ghost" className="p-1" aria-label={`Remove ${file.name}`} onClick={() => removeFile(fileKey(file))}>
                      <X size={14} aria-hidden />
                    </Button>
                  </span>
                </li>
              ))}
            </ul>
          ) : null}

          <div className="grid gap-3 sm:grid-cols-3">
            <label className={FIELD_LABEL}>
              <span className={FIELD_CAPTION}>Version</span>
              <Input value={version} onChange={(event) => setVersion(event.target.value)} placeholder="Automatic" />
            </label>
            <label className={FIELD_LABEL}>
              <span className={FIELD_CAPTION}>Practice owner</span>
              <Input required minLength={2} value={owner} onChange={(event) => setOwner(event.target.value)} placeholder="Name or team" />
            </label>
            <label className={FIELD_LABEL}>
              <span className={FIELD_CAPTION}>Classification</span>
              <Select value={classification} onChange={(event) => setClassification(event.target.value)}>
                {CLASSIFICATION.map((item) => (
                  <option key={item}>{item}</option>
                ))}
              </Select>
            </label>
          </div>
          <label className={FIELD_LABEL}>
            <span className={FIELD_CAPTION}>Source attribution and rights</span>
            <Input required minLength={3} value={rights} onChange={(event) => setRights(event.target.value)} />
          </label>
        </fieldset>

        {note ? <p className="rounded-md bg-[var(--surface-muted)] p-3 text-xs leading-5 text-[var(--text-muted)]">{note}</p> : null}
        <p className="rounded-md bg-[var(--primary-50)] p-3 text-xs leading-5 text-[var(--text-muted)]">
          Uploaded sources remain outside user retrieval until extraction, index validation and quality review are complete and an
          administrator approves and publishes them.
        </p>

        {error ? (
          <p role="alert" className="text-sm text-[var(--error)]">
            {error}
          </p>
        ) : null}
        <ErrorNote error={upload.error} />

        <div className="flex justify-end gap-2 border-t border-[var(--surface-border)] pt-4">
          {onCancel ? (
            <Button type="button" variant="secondary" onClick={onCancel}>
              Cancel
            </Button>
          ) : null}
          <Button type="submit" disabled={upload.isPending}>
            {upload.isPending ? "Uploading…" : "Upload and start extraction"}
          </Button>
        </div>
      </form>
    </Card>
  );
}
