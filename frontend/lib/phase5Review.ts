// Design review (pipeline Phase 5): the run waits until every artifact's current version is approved, or sends one
// back for regeneration. Shapes match src/app/api/phase5_hitl.py.

export type DesignReviewStatus = "pending" | "regenerating" | "approved" | (string & {});

export type DesignReviewArtifact = {
  artifact_type: string;
  version: string;
  status: DesignReviewStatus;
  /** 1 for the first version, plus one per rejection. */
  attempt_count: number;
  rejections_used: number;
  max_rejections: number;
  approved_slides: number[];
  rejected_slides: number[];
  total_slides?: number | null;
};

export type DesignReviewState = {
  run_id: string;
  /** "pending" while the run waits for a decision; then "approved", or "timed_out" if nobody decided. */
  phase_5_status: string | null;
  max_rejections: number;
  artifacts: DesignReviewArtifact[];
};

export type DesignRejectInput = {
  artifact_type: string;
  /** Slide numbers from 1 to regenerate; null regenerates the whole artifact. */
  rejected_slides: number[] | null;
  approved_slides: number[] | null;
  user_feedback?: string;
};

export type DesignReviewResult = { status: string; message: string; new_version?: string | null; attempt?: string | null };

/**
 * Reject body for a deck: the chosen slides are regenerated and the rest kept. Choosing none, or every slide,
 * regenerates the whole deck.
 */
export function buildDeckRejection(totalSlides: number, rejected: number[], feedback: string): DesignRejectInput {
  const all = Array.from({ length: totalSlides }, (_, i) => i + 1);
  const chosen = [...new Set(rejected)].filter((n) => n >= 1 && n <= totalSlides).sort((a, b) => a - b);
  const partial = chosen.length > 0 && chosen.length < totalSlides;
  return {
    artifact_type: "pptx",
    rejected_slides: partial ? chosen : null,
    approved_slides: partial ? all.filter((n) => !chosen.includes(n)) : null,
    user_feedback: feedback.trim() || undefined,
  };
}
