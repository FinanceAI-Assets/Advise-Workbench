"use client";

import { Upload, X } from "lucide-react";
import { type ChangeEvent, type FormEvent, useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Select } from "@/components/ui/Select";
import { ErrorNote } from "@/components/workbench/PageFrame";
import { type LibraryUploadJob, useLibraryUpload } from "@/hooks/useAdminConsole";

const ACCEPTED_SOURCE_TYPES = ".pdf,.docx,.md,.txt";
const MAX_FILE_SIZE = 25 * 1024 * 1024;
const MAX_FILES = 10;
const TAXONOMY = ["Operating model", "Transformation", "Risk & controls", "Change & adoption", "Procurement", "Finance", "Technology"];
const MATURITY = ["Emerging", "Defined", "Managed", "Optimized"];

// Form controls inherit the label's font (globals.css), so the caption styling sits on a span.
const FIELD_LABEL = "grid gap-1.5 text-sm text-[var(--text-default)]";
const FIELD_CAPTION = "text-2xs font-semibold uppercase tracking-wide text-[var(--text-muted)]";

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
    const limit = practice ? 1 : MAX_FILES;
    const invalidFile = selected.find((file) => file.size > MAX_FILE_SIZE);
    if (invalidFile) {
      setError(`${invalidFile.name} exceeds the 25 MB file limit.`);
      event.target.value = "";
      return;
    }
    if (selected.length > limit) {
      setError(practice ? "Attach one corrected source at a time." : `Upload up to ${MAX_FILES} sources at a time.`);
      event.target.value = "";
      return;
    }
    setError(null);
    setFiles(selected);
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (files.length === 0) {
      setError("Select at least one PDF or DOCX source.");
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
    const result = await upload.mutateAsync(form);
    onUploaded(result.jobs);
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
              PDF, DOCX, Markdown or text · Up to 25 MB per file · Text-readable sources required
            </p>
          </div>
          <Button type="button" variant="ghost" className="p-2" aria-label="Close upload sources dialog" onClick={onClose}>
            <X size={18} aria-hidden />
          </Button>
        </div>

        <form className="mt-5 space-y-4" onSubmit={(event) => void submit(event)}>
          <fieldset disabled={upload.isPending} className="space-y-4">
            <label className="block cursor-pointer rounded-md border border-dashed border-[var(--surface-border)] bg-[var(--surface-muted)] p-4 focus-within:ring-2 focus-within:ring-[var(--coral-black)]">
              <span className="flex items-center gap-2 text-sm font-medium text-[var(--text-default)]">
                <Upload size={16} className="text-[var(--accent-green-dark)]" aria-hidden />
                {practice ? "Corrected source file" : "Source files"}
              </span>
              <span className="mt-1 block text-xs text-[var(--text-muted)]">
                {practice
                  ? "The new file replaces the candidate for review; the published version stays live until release."
                  : "Each file becomes a candidate practice. Extraction and validation start on upload."}
              </span>
              <input className="sr-only" type="file" accept={ACCEPTED_SOURCE_TYPES} multiple={!practice} onChange={selectFiles} />
            </label>

            {files.length > 0 ? (
              <ul className="space-y-2" aria-label="Selected source files">
                {files.map((file) => (
                  <li key={`${file.name}-${file.lastModified}`} className="flex items-center justify-between gap-3 text-sm">
                    <span className="truncate font-medium text-[var(--text-default)]">{file.name}</span>
                    <span className="shrink-0 text-xs text-[var(--success)]">Ready · {(file.size / 1024 / 1024).toFixed(1)} MB</span>
                  </li>
                ))}
              </ul>
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
              {upload.isPending ? "Extracting and validating…" : "Start extraction"}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}
