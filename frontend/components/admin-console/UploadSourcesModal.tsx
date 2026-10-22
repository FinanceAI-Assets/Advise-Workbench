"use client";

import { Upload, X } from "lucide-react";
import { type ChangeEvent, type FormEvent, useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Select } from "@/components/ui/Select";

const ACCEPTED_SOURCE_TYPES = ".pdf,.doc,.docx";
const MAX_FILE_SIZE = 25 * 1024 * 1024;

export function UploadSourcesModal({
  onClose,
  onStartExtraction,
}: {
  onClose: () => void;
  onStartExtraction: (fileCount: number) => void;
}) {
  const [files, setFiles] = useState<File[]>([]);
  const [practiceOwner, setPracticeOwner] = useState("");
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
    const invalidFile = selected.find((file) => file.size > MAX_FILE_SIZE);
    if (invalidFile) {
      setError(`${invalidFile.name} exceeds the 25 MB file limit.`);
      event.target.value = "";
      return;
    }
    setError(null);
    setFiles(selected);
  }

  function submit(event: FormEvent) {
    event.preventDefault();
    if (files.length === 0) {
      setError("Select at least one PDF or DOCX source.");
      return;
    }
    onStartExtraction(files.length);
  }

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/45 p-4" onMouseDown={onClose}>
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="upload-sources-title"
        aria-describedby="upload-sources-description"
        tabIndex={-1}
        className="w-full max-w-2xl rounded-lg bg-[var(--surface-default)] p-5 shadow-2xl outline-none"
        onMouseDown={(event) => event.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2 id="upload-sources-title" className="text-lg font-semibold text-[var(--text-default)]">
              Upload sources
            </h2>
            <p id="upload-sources-description" className="mt-1 text-sm text-[var(--text-muted)]">
              PDF or DOCX · Up to 25 MB per file · Text-readable sources required
            </p>
          </div>
          <Button type="button" variant="ghost" className="p-2" aria-label="Close upload sources dialog" onClick={onClose}>
            <X size={18} aria-hidden />
          </Button>
        </div>

        <form className="mt-5 space-y-4" onSubmit={submit}>
          <label className="block rounded-md border border-dashed border-[var(--surface-border)] bg-[var(--surface-muted)] p-4">
            <span className="flex items-center gap-2 text-sm font-medium text-[var(--text-default)]">
              <Upload size={16} className="text-[var(--accent-green-dark)]" aria-hidden />
              Source files
            </span>
            <span className="mt-1 block text-xs text-[var(--text-muted)]">Choose PDF or DOCX files to begin extraction.</span>
            <input
              className="sr-only"
              type="file"
              accept={ACCEPTED_SOURCE_TYPES}
              multiple
              onChange={selectFiles}
            />
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

          <div className="grid gap-3 sm:grid-cols-2">
            <label className="grid gap-1.5 text-2xs font-semibold uppercase tracking-wide text-[var(--text-muted)]">
              Practice owner
              <Input value={practiceOwner} onChange={(event) => setPracticeOwner(event.target.value)} placeholder="Name or team" />
            </label>
            <label className="grid gap-1.5 text-2xs font-semibold uppercase tracking-wide text-[var(--text-muted)]">
              Classification
              <Select value={classification} onChange={(event) => setClassification(event.target.value)}>
                <option>Internal methods content</option>
                <option>Confidential</option>
                <option>Public reference</option>
              </Select>
            </label>
          </div>

          <label className="grid gap-1.5 text-2xs font-semibold uppercase tracking-wide text-[var(--text-muted)]">
            Source attribution and rights
            <Input value={rights} onChange={(event) => setRights(event.target.value)} />
          </label>

          <div className="rounded-md bg-[var(--primary-50)] p-3 text-xs leading-5 text-[var(--text-muted)]">
            Uploaded sources remain outside user retrieval until extraction, index validation, quality review, and independent
            approval are complete.
          </div>

          {error ? <p role="alert" className="text-sm text-[var(--error)]">{error}</p> : null}

          <div className="flex justify-end gap-2 border-t border-[var(--surface-border)] pt-4">
            <Button type="button" variant="secondary" onClick={onClose}>
              Cancel
            </Button>
            <Button type="submit">Start extraction</Button>
          </div>
        </form>
      </div>
    </div>
  );
}
