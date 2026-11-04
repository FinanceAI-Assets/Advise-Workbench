"use client";

import { useCallback, useEffect, useState } from "react";

import { Button } from "@/components/ui/Button";
import { useAuth } from "@/lib/auth-context";

// Mirrors `ingestion` in src/app/api/documents.py: the ingestion pipeline's processing of one upload.
type Ingestion = {
  job_id: string;
  status: string;
  searchable: boolean;
  is_terminal: boolean;
  stage: string | null;
  progress_percent: number;
  chunk_count: number;
  error: string | null;
};

type DocumentItem = { filename: string; path: string; ingestion: Ingestion | null };

const POLL_MS = 3000;

function IngestionBadge({ ingestion, onRetry, retrying }: { ingestion: Ingestion | null; onRetry: () => void; retrying: boolean }) {
  if (!ingestion) {
    return (
      <button type="button" className="text-[var(--info)] underline" onClick={onRetry} disabled={retrying}>
        {retrying ? "Queuing..." : "Not processed - process now"}
      </button>
    );
  }
  if (ingestion.searchable) {
    return <span className="text-[var(--success)]">Ready for questions</span>;
  }
  if (ingestion.status === "failed") {
    return (
      <span className="flex items-center gap-2 text-[var(--error)]" title={ingestion.error ?? undefined}>
        Processing failed
        <button type="button" className="underline" onClick={onRetry} disabled={retrying}>
          {retrying ? "Retrying..." : "Retry"}
        </button>
      </span>
    );
  }
  return (
    <span className="text-[var(--info)]">
      Processing{ingestion.stage ? ` (${ingestion.stage})` : ""} {ingestion.progress_percent}%
    </span>
  );
}

export function DocumentUploader({ projectId, autoload = true }: { projectId: string; autoload?: boolean }) {
  const { api, token, ready } = useAuth();
  const [items, setItems] = useState<DocumentItem[]>([]);
  const [retrying, setRetrying] = useState(false);
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [deleting, setDeleting] = useState<string | null>(null);
  const [selectedFileName, setSelectedFileName] = useState<string | null>(null);
  const [uploadProgress, setUploadProgress] = useState<{ index: number; total: number } | null>(null);

  const loadDocuments = useCallback(
    async (quiet = false) => {
      if (!projectId || !token) return;
      if (!quiet) {
        setLoading(true);
        setError(null);
      }
      try {
        const res = await api(`/api/documents/list?project_id=${encodeURIComponent(projectId)}`);
        const data = (await res.json().catch(() => ({}))) as {
          items?: string[];
          documents?: DocumentItem[];
          detail?: string;
        };
        if (!res.ok) {
          throw new Error(typeof data.detail === "string" ? data.detail : "Failed to load documents");
        }
        if (Array.isArray(data.documents)) {
          setItems(data.documents);
        } else {
          const paths = Array.isArray(data.items) ? data.items : [];
          setItems(paths.map((p) => ({ filename: p.split("/").pop() ?? p, path: p, ingestion: null })));
        }
      } catch (e) {
        if (!quiet) setError(e instanceof Error ? e.message : "Failed to load documents");
      } finally {
        if (!quiet) setLoading(false);
      }
    },
    [api, projectId, token]
  );

  useEffect(() => {
    if (!autoload || !projectId || !ready || !token) return;
    void loadDocuments();
  }, [projectId, autoload, ready, token, loadDocuments]);

  // Uploads are processed in the background; refresh their status until every one is done.
  const processing = items.some((d) => d.ingestion && !d.ingestion.is_terminal);
  useEffect(() => {
    if (!processing) return;
    const timer = window.setInterval(() => void loadDocuments(true), POLL_MS);
    return () => window.clearInterval(timer);
  }, [processing, loadDocuments]);

  async function handleReprocess() {
    if (!projectId || !token) return;
    setRetrying(true);
    setError(null);
    try {
      const res = await api(`/api/documents/reindex?project_id=${encodeURIComponent(projectId)}`, { method: "POST" });
      const data = (await res.json().catch(() => ({}))) as { detail?: string };
      if (!res.ok) {
        throw new Error(typeof data.detail === "string" ? data.detail : "Could not queue the documents");
      }
      await loadDocuments(true);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not queue the documents");
    } finally {
      setRetrying(false);
    }
  }

  async function handleUploadOne(file: File): Promise<{ filename: string; ok: boolean; error?: string }> {
    const filename = file.name;
    try {
      const form = new FormData();
      form.append("project_id", projectId);
      form.append("file", file);
      const res = await api("/api/documents/upload", {
        method: "POST",
        body: form,
        headers: {},
      });
      const data = (await res.json().catch(() => ({}))) as {
        filename?: string;
        detail?: string;
      };
      if (!res.ok) {
        throw new Error(typeof data.detail === "string" ? data.detail : "Upload failed");
      }
      setMessage(`Uploaded: ${filename} - processing for questions`);
      await loadDocuments(true);

      // Ingest document into wiki (non-blocking — wiki page auto-syncs on load too)
      try {
        const params = new URLSearchParams({
          source_type: "document",
          project_id: projectId,
        });
        const wikiRes = await api(`/api/wiki/project/ingest?${params}`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ source_data: { filename } }),
        });
        if (wikiRes.ok) {
          setMessage(`Uploaded: ${filename} — added to wiki`);
        } else {
          setMessage(`Uploaded: ${filename} — wiki sync pending (open Wiki to sync)`);
        }
      } catch {
        setMessage(`Uploaded: ${filename} — wiki sync pending (open Wiki to sync)`);
      }
      return { filename, ok: true };
    } catch (e) {
      return { filename, ok: false, error: e instanceof Error ? e.message : "Upload failed" };
    }
  }

  async function handleUpload(files: FileList | null) {
    if (!projectId || !files || files.length === 0 || !token) return;
    const fileList = Array.from(files);
    setUploading(true);
    setError(null);
    setMessage(null);

    const failures: string[] = [];
    for (let i = 0; i < fileList.length; i++) {
      setUploadProgress({ index: i + 1, total: fileList.length });
      const result = await handleUploadOne(fileList[i]);
      if (!result.ok) {
        failures.push(`${result.filename}: ${result.error ?? "Upload failed"}`);
      }
    }

    setUploadProgress(null);
    if (failures.length > 0) {
      setError(`Some uploads failed — ${failures.join("; ")}`);
    }
    if (failures.length < fileList.length) {
      const succeeded = fileList.length - failures.length;
      setMessage(`Uploaded ${succeeded} of ${fileList.length} document${fileList.length > 1 ? "s" : ""}`);
    }
    setUploading(false);
  }

  async function handleDelete(filename: string) {
    if (!projectId || !token) return;
    setDeleting(filename);
    setError(null);
    setMessage(null);
    try {
      const res = await api(
        `/api/documents/delete?project_id=${encodeURIComponent(projectId)}&filename=${encodeURIComponent(filename)}`,
        {
          method: "DELETE",
        }
      );
      const data = (await res.json().catch(() => ({}))) as { detail?: string; deleted?: boolean; filename?: string };
      if (!res.ok || !data.deleted) {
        throw new Error(typeof data.detail === "string" ? data.detail : "Delete failed");
      }
      setMessage(`Deleted: ${data.filename ?? filename}`);
      await loadDocuments();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Delete failed");
    } finally {
      setDeleting(null);
    }
  }

  return (
    <div className="space-y-3 rounded-lg border border-[var(--surface-border)] bg-white p-4">
      <div className="flex items-center justify-between">
        <h3 className="text-base font-semibold">Project documents</h3>
        <Button type="button" variant="secondary" onClick={() => void loadDocuments()} disabled={loading || uploading}>
          {loading ? "Refreshing..." : "Refresh"}
        </Button>
      </div>
      <label className="inline-flex cursor-pointer items-center gap-2 text-sm">
        <input
          type="file"
          multiple
          className="hidden"
          disabled={uploading}
          onChange={(e) => {
            const selected = e.target.files;
            setSelectedFileName(
              selected && selected.length > 0
                ? selected.length === 1
                  ? selected[0].name
                  : `${selected.length} files selected`
                : null
            );
            void handleUpload(selected);
            e.currentTarget.value = "";
          }}
        />
        <span className="rounded-md border border-[color:color-mix(in_srgb,var(--primary-700)_35%,transparent)] bg-white px-3 py-2 text-sm text-[var(--primary-900)] hover:bg-[var(--primary-50)]">
          {uploading ? "Uploading..." : "Choose files"}
        </span>
        <span className="text-xs text-[var(--text-muted)]">{selectedFileName ?? "No file selected"}</span>
      </label>
      {uploading ? (
        <p className="text-xs text-[var(--info)]">
          {uploadProgress ? `Uploading document ${uploadProgress.index} of ${uploadProgress.total}...` : "Uploading document..."}
        </p>
      ) : null}
      {message ? <p className="text-xs text-[var(--success)]">{message}</p> : null}
      {error ? <p className="text-xs text-[var(--error)]">{error}</p> : null}
      <div className="space-y-2 text-xs text-[var(--text-muted)]">
        {items.length === 0 ? (
          <p>No documents uploaded yet.</p>
        ) : (
          items.map((item) => (
            <div key={item.path} className="flex items-center justify-between gap-2 rounded border border-[var(--surface-border)] bg-[var(--surface-muted)] px-2 py-1">
              <p className="truncate">{item.filename}</p>
              <div className="flex shrink-0 items-center gap-3">
                <IngestionBadge ingestion={item.ingestion} onRetry={() => void handleReprocess()} retrying={retrying} />
                <Button
                  type="button"
                  variant="secondary"
                  className="px-2 py-1 text-xs"
                  disabled={Boolean(deleting)}
                  onClick={() => void handleDelete(item.filename)}
                >
                  {deleting === item.filename ? "Deleting..." : "Delete"}
                </Button>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
