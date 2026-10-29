"use client";

import { Upload, X } from "lucide-react";
import { type ChangeEvent, type DragEvent, type FormEvent, useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Select } from "@/components/ui/Select";
import { ErrorNote } from "@/components/workbench/PageFrame";
import { cn } from "@/lib/utils";
import { type LibraryUploadJob, useLibraryUpload } from "@/hooks/useAdminConsole";

// Keep in step with SUPPORTED_EXTENSIONS in src/memory/knowledge/practice_ingest.py.
const ACCEPTED_EXTENSIONS = [".pdf", ".docx", ".pptx", ".xlsx", ".md", ".txt"];
const ACCEPTED_SOURCE_TYPES = ACCEPTED_EXTENSIONS.join(",");
// Office 97-2003 formats the server cannot read; the admin is asked to re-save them.
const LEGACY_OFFICE: Record<string, string> = { ".doc": ".docx", ".ppt": ".pptx", ".xls": ".xlsx" };
const MAX_FILE_SIZE = 25 * 1024 * 1024;
const MAX_FILES = 10;
const TAXONOMY = ["Operating model", "Transformation", "Risk & controls", "Change & adoption", "Procurement", "Finance", "Technology"];
const MATURITY = ["Emerging", "Defined", "Managed", "Optimized"];

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

/**
 * Upload practice sources into the library pipeline. With `practice`, the single file is a corrected source
 * or a new version of that practice; otherwise each file starts a new candidate practice.
 */
export function UploadSourcesModal({
  practice,
  onClose,
  onUploaded,
}: {
  practice?: { id: string; title: string; owner?: string };
  onClose: () => void;
  onUploaded: (jobs: LibraryUploadJob[]) => void;
}) {
  const upload = useLibraryUpload();
  const [files, setFiles] = useState<File[]>([]);
  const [title, setTitle] = useState("");
  const [practiceOwner, setPracticeOwner] = useState(practice?.owner ?? "");
  const [category, setCategory] = useState(TAXONOMY[0]);
  const [maturity, setMaturity] = useState("Defined");
  const [version, setVersion] = useState("");
  const [classification, setClassification] = useState("Internal methods content");
  const [rights, setRights] = useState("Advisory Methods team · Internal reuse permitted");
  const [error, setError] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);
  const dialogRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    dialogRef.current?.focus();
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [onClose]);

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

  /** Files from the picker or a drop: checked, then added to the list (a correction replaces its one file). */
  function addFiles(selected: File[]) {
    if (selected.length === 0) return;
    if (practice && selected.length > 1) {
      setError("Attach one corrected source at a time.");
      return;
    }
    const rejection = selected.map(rejectionFor).find(Boolean);
    if (rejection) {
      setError(rejection);
      return;
    }
    // A correction replaces its single file; new sources add to the list, so files can come from several folders.
    const known = new Set(files.map(fileKey));
    const next = practice ? selected : [...files, ...selected.filter((file) => !known.has(fileKey(file)))];
    if (next.length > (practice ? 1 : MAX_FILES)) {
      setError(practice ? "Attach one corrected source at a time." : `Upload up to ${MAX_FILES} sources at a time.`);
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
      setError("Select at least one PDF, Word, PowerPoint or Excel source.");
      return;
    }
    const form = new FormData();
    files.forEach((file) => form.append("files", file));
    form.append("owner", practiceOwner.trim());
    form.append("classification", classification);
    form.append("rights", rights.trim());
    // A corrected source keeps the candidate's taxonomy and maturity.
    if (!practice) {
      form.append("category", category);
      form.append("maturity", maturity);
    }
    if (version.trim()) form.append("version", version.trim());
    if (practice) form.append("practice_id", practice.id);
    else if (files.length === 1 && title.trim()) form.append("title", title.trim());
    try {
      const result = await upload.mutateAsync(form);
      onUploaded(result.jobs);
    } catch {
      // upload.error is shown in the dialog (ErrorNote below).
    }
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
        aria-labelledby="upload-sources-title"
        aria-describedby="upload-sources-description"
        tabIndex={-1}
        className="max-h-[calc(100vh-2rem)] w-full max-w-2xl overflow-y-auto rounded-lg bg-[var(--surface-default)] p-5 shadow-2xl outline-none"
      >
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2 id="upload-sources-title" className="text-lg font-semibold text-[var(--text-default)]">
              {practice ? `Upload corrected source · ${practice.title}` : "Upload sources"}
            </h2>
            <p id="upload-sources-description" className="mt-1 text-sm text-[var(--text-muted)]">
              PDF, Word, PowerPoint, Excel, Markdown or text · {practice ? "One file" : `Up to ${MAX_FILES} files`}, 25 MB
              each · Text-readable sources required
            </p>
          </div>
          <Button type="button" variant="ghost" className="p-2" aria-label="Close upload sources dialog" onClick={onClose}>
            <X size={18} aria-hidden />
          </Button>
        </div>

        <form className="mt-5 space-y-4" onSubmit={(event) => void submit(event)}>
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
                  "block cursor-pointer rounded-md border border-dashed p-5 text-center transition focus-within:ring-2 focus-within:ring-[var(--coral-black)]",
                  dragging
                    ? "border-[var(--accent-green)] bg-[#EFF6E6]"
                    : "border-[var(--surface-border-strong)] bg-[var(--surface-muted)] hover:border-[var(--accent-green)]"
                )}
              >
                <Upload size={20} className="mx-auto text-[var(--accent-green-dark)]" aria-hidden />
                <span className="mt-2 block text-sm font-medium text-[var(--text-default)]">
                  {practice ? "Drag and drop the corrected file here, or " : "Drag and drop files here, or "}
                  <span className="text-[var(--accent-green-dark)] underline underline-offset-2">browse</span>
                </span>
                <span className="mt-1 block text-xs text-[var(--text-muted)]">
                  {practice
                    ? "The new file replaces the candidate for review; the published version stays live until release."
                    : `Select up to ${MAX_FILES} files at once (hold Ctrl or Shift), or add more in several picks. Each file becomes a candidate practice.`}
                </span>
                <input className="sr-only" type="file" accept={ACCEPTED_SOURCE_TYPES} multiple={!practice} onChange={selectFiles} />
              </label>
            </div>

            {files.length > 0 ? (
              <div className="space-y-2">
                {!practice ? (
                  <p className="text-xs text-[var(--text-muted)]" aria-live="polite">
                    {files.length} of {MAX_FILES} files selected · extraction and validation start on upload
                  </p>
                ) : null}
                <ul className="space-y-2" aria-label="Selected source files">
                  {files.map((file) => (
                    <li key={fileKey(file)} className="flex items-center justify-between gap-3 text-sm">
                      <span className="truncate font-medium text-[var(--text-default)]">{file.name}</span>
                      <span className="flex shrink-0 items-center gap-2">
                        <span className="text-xs text-[var(--success)]">Ready · {formatSize(file.size)}</span>
                        <Button
                          type="button"
                          variant="ghost"
                          className="p-1"
                          aria-label={`Remove ${file.name}`}
                          onClick={() => removeFile(fileKey(file))}
                        >
                          <X size={14} aria-hidden />
                        </Button>
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}

            {!practice ? (
              <label className={FIELD_LABEL}>
                <span className={FIELD_CAPTION}>Practice title</span>
                <Input
                  value={title}
                  onChange={(event) => setTitle(event.target.value)}
                  placeholder={files.length > 1 ? "Taken from each file name" : "Defaults to the file name"}
                  disabled={files.length > 1}
                />
              </label>
            ) : null}

            <div className={practice ? "grid gap-3" : "grid gap-3 sm:grid-cols-3"}>
              {!practice ? (
              <>
              <label className={FIELD_LABEL}>
                <span className={FIELD_CAPTION}>Taxonomy</span>
                <Select value={category} onChange={(event) => setCategory(event.target.value)}>
                  {TAXONOMY.map((item) => (
                    <option key={item}>{item}</option>
                  ))}
                </Select>
              </label>
              <label className={FIELD_LABEL}>
                <span className={FIELD_CAPTION}>Maturity</span>
                <Select value={maturity} onChange={(event) => setMaturity(event.target.value)}>
                  {MATURITY.map((item) => (
                    <option key={item}>{item}</option>
                  ))}
                </Select>
              </label>
              </>
              ) : null}
              <label className={FIELD_LABEL}>
                <span className={FIELD_CAPTION}>Version</span>
                <Input value={version} onChange={(event) => setVersion(event.target.value)} placeholder={practice ? "Automatic" : "v1.0"} />
              </label>
            </div>

            <div className="grid gap-3 sm:grid-cols-2">
              <label className={FIELD_LABEL}>
                <span className={FIELD_CAPTION}>Practice owner</span>
                <Input required minLength={2} value={practiceOwner} onChange={(event) => setPracticeOwner(event.target.value)} placeholder="Name or team" />
              </label>
              <label className={FIELD_LABEL}>
                <span className={FIELD_CAPTION}>Classification</span>
                <Select value={classification} onChange={(event) => setClassification(event.target.value)}>
                  <option>Internal methods content</option>
                  <option>Confidential</option>
                  <option>Public reference</option>
                </Select>
              </label>
            </div>

            <label className={FIELD_LABEL}>
              <span className={FIELD_CAPTION}>Source attribution and rights</span>
              <Input required minLength={3} value={rights} onChange={(event) => setRights(event.target.value)} />
            </label>
          </fieldset>

          <div className="rounded-md bg-[var(--primary-50)] p-3 text-xs leading-5 text-[var(--text-muted)]">
            Uploaded sources remain outside user retrieval until extraction, index validation, quality review, and independent
            approval are complete.
          </div>

          {error ? <p role="alert" className="text-sm text-[var(--error)]">{error}</p> : null}
          <ErrorNote error={upload.error} />

          <div className="flex justify-end gap-2 border-t border-[var(--surface-border)] pt-4">
            <Button type="button" variant="secondary" onClick={onClose}>
              Cancel
            </Button>
            <Button type="submit" disabled={upload.isPending}>
              {upload.isPending ? "Uploading…" : "Start extraction"}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}
