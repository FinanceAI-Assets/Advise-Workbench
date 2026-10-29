"use client";

import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { useAuth } from "@/lib/auth-context";
import { fetchJson } from "@/lib/workbenchApi";
import type {
  AdminEngagementsDetail,
  AdminLibraryDetail,
  AdminOverviewDetail,
  AdminReviewsGovernanceDetail,
  AuditTrailEvent,
  RiskQueueRow,
  SelectedEngagementDetail,
  SelectedReviewGovernanceDetail,
} from "@/types/api";

// Admin console data. Every endpoint is under /api/admin and requires an administrator.

export type AdminRecord = { id: string } & Record<string, string>;

export type AdminOverview = AdminOverviewDetail & { ingestionJobs: AdminRecord[] };

export type AdminEngagements = Omit<AdminEngagementsDetail, "selected"> & {
  selected: (SelectedEngagementDetail & { retentionDays: number; status: string; archiveReady: boolean }) | null;
  deliverables: AdminRecord[];
  retentionExceptions: AdminRecord[];
  exportRequests: AdminRecord[];
  roles: string[];
};

export type AdminLibrary = AdminLibraryDetail & {
  ingestionJobs: AdminRecord[];
  /** Pipeline status of the selected practice's latest upload (null for the sample walkthrough). */
  ingestion?: IngestionJobStatus | null;
};

export type AdminReviews = Omit<AdminReviewsGovernanceDetail, "selectedReview"> & {
  selectedReview: (SelectedReviewGovernanceDetail & { reviewerId: string | null; ownerId: string | null }) | null;
  risks: RiskQueueRow[];
  fullAuditTrail: AuditTrailEvent[];
  reviewers: Array<{ id: string; name: string }>;
};

function useAdminQuery<T>(key: unknown[], path: string, { keepPrevious = false } = {}) {
  const { api, token, user } = useAuth();
  return useQuery({
    queryKey: ["admin", ...key],
    enabled: Boolean(token) && Boolean(user),
    staleTime: 15 * 1000,
    // Switching the selection keeps the current screen up while the next one loads.
    placeholderData: keepPrevious ? keepPreviousData : undefined,
    queryFn: () => fetchJson<T>(api, path, "Failed to load the admin console"),
  });
}

export const useAdminOverviewQuery = () => useAdminQuery<AdminOverview>(["overview"], "/api/admin/overview");

export const useAdminEngagementsQuery = (q: string, selected: string) =>
  useAdminQuery<AdminEngagements>(
    ["engagements", q, selected],
    `/api/admin/engagements?q=${encodeURIComponent(q)}&selected=${encodeURIComponent(selected)}`
  );

/** The library pipeline for one practice; with no practice, the latest upload (or the sample walkthrough). */
export const useAdminLibraryQuery = (practice = "") =>
  useAdminQuery<AdminLibrary>(["library", practice], `/api/admin/library?practice=${encodeURIComponent(practice)}`, {
    keepPrevious: true,
  });

/** One uploaded file as queued on the ingestion pipeline; poll `job_id` for its progress. */
export type QueuedIngestion = {
  job_id: string | null;
  status: string;
  filename: string;
  file_size_bytes: number;
  sha256: string;
  timestamp: string;
  message: string;
};

/**
 * One file of an upload. `id` and `practiceId` are empty strings when intake has not run yet;
 * an identical re-upload comes back with `ingestion.status` "unchanged" and is not processed again.
 */
export type LibraryUploadJob = {
  id: string;
  practiceId: string;
  stage: string;
  outcome: string;
  readable: boolean | null;
  ingestion?: QueuedIngestion;
};

/** Upload practice sources: each file is queued on the ingestion pipeline and processed in the background. */
export function useLibraryUpload() {
  const { api } = useAuth();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (form: FormData) =>
      fetchJson<{ jobs: LibraryUploadJob[] }>(api, "/api/admin/library/uploads", "The sources could not be uploaded", {
        method: "POST",
        body: form,
      }),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ["admin"] }),
  });
}

/** Ingestion jobs to follow after an upload: every file that was queued (not an unchanged re-upload). */
export const queuedJobIds = (jobs: LibraryUploadJob[]) =>
  jobs.flatMap((job) => (job.ingestion?.job_id && job.ingestion.status !== "unchanged" ? [job.ingestion.job_id] : []));

// Mirrors JobStatus in src/app/api/documents_async.py.
export type IngestionJobStatus = {
  job_id: string;
  status: string;
  is_terminal: boolean;
  practice_id: string | null;
  filename: string;
  stages: string[];
  /** -1 before the first stage; stages.length once completed. */
  current_stage_index: number;
  progress_percent: number;
  document_file_id: string | null;
  counts: { chunks: number; embeddings: number; facts: number; wiki_pages: number };
  chunk_count: number;
  created_at: string;
  updated_at: string;
  completed_at: string | null;
  file_size_bytes: number | null;
  sha256: string | null;
  parse_mode: string | null;
  text_length: number | null;
  failed_stage: string | null;
  error_message: string | null;
};

export type IngestionJobDetails = {
  job: IngestionJobStatus;
  seaweedfs: { bucket: string; key: string; object?: Record<string, unknown>; error?: string } | null;
  postgres: {
    document_file_id: string;
    parsed_document_id: string | null;
    page_count: number | null;
    table_count: number | null;
    text_length: number | null;
    chunk_count: number;
    reused_chunk_count: number;
    chunks: Array<{
      id: string;
      chunk_number: number;
      page_number: number | null;
      source_type: string;
      characters: number;
      reused: boolean;
      preview: string;
    }>;
  } | null;
  qdrant: {
    collection?: string;
    points_for_document?: number;
    wiki_collection?: string;
    wiki_points_in_project?: number;
    error?: string;
  } | null;
  knowledge: {
    fact_count: number;
    facts: Array<{ type: string; name: string; confidence: number | null; context: string | null }>;
    wiki_pages: Array<{ id: string; entity_name: string; entity_type: string; merge_count: number; is_published: boolean; content: string }>;
  } | null;
};

const POLL_MS = 3000;

/** Live progress of one ingestion job, polled every 3 seconds until it is terminal; then the library view refreshes. */
export function useIngestionJobStatus(jobId: string | null) {
  const { api, token, user } = useAuth();
  const qc = useQueryClient();
  return useQuery({
    queryKey: ["admin", "ingestion", "status", jobId],
    enabled: Boolean(token) && Boolean(user) && Boolean(jobId),
    queryFn: async () => {
      const status = await fetchJson<IngestionJobStatus>(
        api,
        `/api/admin/library/documents/status/${encodeURIComponent(jobId ?? "")}`,
        "The upload progress could not be loaded",
      );
      if (status.is_terminal) {
        void qc.invalidateQueries({ queryKey: ["admin", "library"] });
        void qc.invalidateQueries({ queryKey: ["admin", "ingestion", "jobs"] });
      }
      return status;
    },
    refetchInterval: (query) => (query.state.data?.is_terminal || query.state.error ? false : POLL_MS),
  });
}

/** Every Library upload (latest job per document) with its status and counts; refreshes while any is running. */
export function useLibraryIngestionJobs() {
  const { api, token, user } = useAuth();
  return useQuery({
    queryKey: ["admin", "ingestion", "jobs"],
    enabled: Boolean(token) && Boolean(user),
    queryFn: () => fetchJson<IngestionJobStatus[]>(api, "/api/admin/library/documents/jobs", "The uploads could not be loaded"),
    refetchInterval: (query) => (query.state.data?.some((job) => !job.is_terminal) ? POLL_MS : false),
  });
}

/** What the pipeline stored for one file: S3 object, Postgres chunks, Qdrant vectors, facts and wiki pages. */
export function useIngestionJobDetails(jobId: string | null | undefined) {
  const { api, token, user } = useAuth();
  return useQuery({
    queryKey: ["admin", "ingestion", "details", jobId],
    enabled: Boolean(token) && Boolean(user) && Boolean(jobId),
    staleTime: 15 * 1000,
    queryFn: () =>
      fetchJson<IngestionJobDetails>(
        api,
        `/api/admin/library/documents/${encodeURIComponent(jobId ?? "")}/details`,
        "The stored data could not be loaded",
      ),
  });
}

/** Delete a practice with all of its uploads and pipeline data (S3, chunks, vectors, facts, wiki). */
export function useDeletePractice() {
  const { api } = useAuth();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (practiceId: string) =>
      fetchJson<{ deleted: string; sources_removed: number; search_documents_removed: number }>(
        api,
        `/api/admin/library/${encodeURIComponent(practiceId)}`,
        "The practice could not be deleted",
        { method: "DELETE" },
      ),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ["admin"] }),
  });
}


export const useAdminReviewsQuery = (selected: string) =>
  useAdminQuery<AdminReviews>(["reviews", selected], `/api/admin/reviews?selected=${encodeURIComponent(selected)}`);

/** One administrative change. `path` is relative to /api/admin; every change refreshes the console. */
export type AdminAction = { path: string; method?: "POST" | "PUT"; body: Record<string, unknown> };

export function useAdminAction() {
  const { api } = useAuth();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (action: AdminAction) =>
      fetchJson(api, `/api/admin${action.path}`, "The change could not be saved", {
        method: action.method ?? "POST",
        body: JSON.stringify(action.body),
      }),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ["admin"] }),
  });
}
