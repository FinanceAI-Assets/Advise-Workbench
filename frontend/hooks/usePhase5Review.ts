"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { extractApiErrorMessage } from "@/lib/api-error";
import { useAuth } from "@/lib/auth-context";
import { buildDeckRejection, type DesignRejectInput, type DesignReviewResult, type DesignReviewState } from "@/lib/phase5Review";
import { fetchJson } from "@/lib/workbenchApi";

const enc = encodeURIComponent;

/**
 * Design review (Phase 5) state of one run. Null while the run has not reached design review, which the API
 * reports as 404. Checks every 15 seconds until the run reaches review, and every 5 while a version is regenerated.
 */
export function useDesignReviewQuery(runId: string) {
  const { api, token } = useAuth();
  return useQuery({
    queryKey: ["design-review", runId],
    enabled: Boolean(token) && Boolean(runId),
    staleTime: 5 * 1000,
    queryFn: async (): Promise<DesignReviewState | null> => {
      const res = await api(`/api/runs/${enc(runId)}/phase5/approval-status`);
      const data = (await res.json().catch(() => ({}))) as DesignReviewState;
      if (res.status === 404) return null;
      if (!res.ok) throw new Error(extractApiErrorMessage(data, "Could not load the design review"));
      return { ...data, artifacts: data.artifacts ?? [] };
    },
    refetchInterval: (query) => {
      const data = query.state.data;
      if (data === null) return 15000;
      return data?.artifacts.some((a) => a.status === "regenerating") ? 5000 : false;
    },
  });
}

function useDesignReviewMutation<TBody>(runId: string, path: string, fallback: string) {
  const { api } = useAuth();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: TBody) =>
      fetchJson<DesignReviewResult>(api, `/api/runs/${enc(runId)}/phase5/${path}`, fallback, {
        method: "POST",
        body: JSON.stringify(body),
      }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["design-review", runId] });
      void qc.invalidateQueries({ queryKey: ["deliverables"] });
    },
  });
}

/** Approve one artifact's current version; the run moves on once every artifact is approved. */
export function useApproveDesignMutation(runId: string) {
  return useDesignReviewMutation<{ artifact_type: string }>(runId, "approve", "Could not approve the artifact");
}

/** Send one artifact back for regeneration: a deck by slide, everything else whole. */
export function useRejectDesignMutation(runId: string) {
  return useDesignReviewMutation<DesignRejectInput>(runId, "reject", "Could not send the artifact back");
}

/** What an artifact's approve and reject buttons need to answer a run waiting in design review. */
export type ArtifactDesignReview = {
  artifactType: string;
  /** The run is waiting for this decision. */
  waiting: boolean;
  regenerating: boolean;
  /** Slides rebuilt by a partial deck regeneration in progress; empty for a whole rebuild. */
  rebuildingSlides: number[];
  approved: boolean;
  version: string;
  /** Why rejecting is unavailable, when it is. */
  rejectBlocked: string | null;
  busy: boolean;
  error: unknown;
  approve: () => Promise<unknown>;
  /** Regenerate these slides of a deck, or the whole artifact when null. */
  reject: (slides: number[] | null, feedback: string) => Promise<unknown>;
};

/** Kept for the deck buttons, which only ever review the deck. */
export type DeckDesignReview = ArtifactDesignReview;

/**
 * Design review state of one artifact of a run, or null when it has none. `types` lists the review types that
 * can stand for it, first match wins (a Word draft is reviewed as docx, narrative or sop).
 */
export function useArtifactDesignReview(runId: string, types: string[], totalSlides = 0): ArtifactDesignReview | null {
  const review = useDesignReviewQuery(runId);
  const approve = useApproveDesignMutation(runId);
  const reject = useRejectDesignMutation(runId);
  const record = types.map((t) => review.data?.artifacts.find((a) => a.artifact_type === t)).find(Boolean);
  if (!review.data || !record) return null;
  const type = record.artifact_type;
  const limitReached = record.rejections_used >= record.max_rejections;
  return {
    artifactType: type,
    waiting: review.data.phase_5_status === "pending",
    regenerating: record.status === "regenerating",
    rebuildingSlides: record.status === "regenerating" ? record.rejected_slides : [],
    approved: record.status === "approved",
    version: record.version,
    rejectBlocked: limitReached ? `Rejection limit reached (${record.max_rejections}/${record.max_rejections}): approve this version` : null,
    busy: approve.isPending || reject.isPending,
    error: approve.error ?? reject.error,
    approve: () => approve.mutateAsync({ artifact_type: type }),
    reject: (slides, feedback) =>
      reject.mutateAsync(
        type === "pptx" && slides && slides.length < totalSlides
          ? buildDeckRejection(totalSlides, slides, feedback)
          : { artifact_type: type, rejected_slides: null, approved_slides: null, user_feedback: feedback.trim() || undefined }
      ),
  };
}

/** The deck's design review state for a run, or null when the run has none. */
export function useDeckDesignReview(runId: string, totalSlides: number): DeckDesignReview | null {
  return useArtifactDesignReview(runId, ["pptx"], totalSlides);
}
