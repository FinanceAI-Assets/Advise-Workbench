"use client";

import { useQuery } from "@tanstack/react-query";

import { extractApiErrorMessage } from "@/lib/api-error";
import { useAuth } from "@/lib/auth-context";
import { splitMarkdownSections, toSlideDetail, type RawPptxSlide } from "@/lib/deliverableAdapters";
import type {
  ArtifactStatus,
  DeliverablesDetail,
  EngagementFile,
  Slide,
  SlideEvidenceLink,
  VersionHistoryEntry,
} from "@/types/api";

// Real-backend deliverables hook, scoped by (pid, runId?) instead of the
// mock's hardcoded "ns-042". Reuses the already-real run/artifact endpoints
// (useRuns.ts's GET /api/runs, the existing GET /api/runs/{pid}/{runId}/artifacts)
// plus the additive canvas-history and already-real evidence-claims routes.

type RunRow = { id: string; status: string; created_at: string | null; instruction: string };

type RunArtifactsBag = {
  pptx_slides?: RawPptxSlide[];
  narrative_md?: string;
  docx_base64?: string;
  sop_markdown?: string;
  evidence_claims?: { claims?: Array<Record<string, unknown>>; summary?: Record<string, number> };
  ready_downloads?: string[];
  quality_status?: string;
} & Record<string, unknown>;

type RunArtifactsResponse = {
  run_id: string;
  project_id: string;
  status: string;
  instruction: string;
  artifacts: RunArtifactsBag | null;
};

type CanvasHistoryItem = { id: string; version: string; current: boolean; meta: string };
type CanvasHistoryResponse = { items: CanvasHistoryItem[] };

// Raw shape of one row from GET /api/runs/{pid}/{rid}/evidence-claims — see
// build_claims_from_evidence_report in src/evaluation/evidence_claims.py.
type RawEvidenceClaim = {
  id?: string;
  slide_index?: number;
  slide_title?: string;
  claim?: string;
  claim_type?: string;
  status?: "unsupported" | "grounded";
  citation?: string | null;
};

function statusFromQuality(quality: string | undefined): ArtifactStatus {
  if (quality === "passed") return "Approved";
  if (quality === "review_recommended" || quality === "completed_with_guardrail_failures") return "Changes requested";
  return "Draft";
}

// Extra, non-mock fields the Deliverables page uses to build a
// per-slide-index detail callback for ArtifactViewer (so browsing slides
// shows real content, not just the initially-active one), and per-slide
// evidence links (so the "Evidence linked to this slide" panel reflects
// whichever slide is currently selected, not just slide 0).
export type DeliverablesWithRaw = DeliverablesDetail & {
  runId: string;
  rawSlides: RawPptxSlide[];
  slideBreadcrumb: string;
  slideSourcesSummary: string;
  slideFooterMeta: string;
  claimsBySlideIndex: Record<number, SlideEvidenceLink[]>;
};

export function useDeliverablesQuery(pid: string, runId?: string, enabled = true) {
  const { api, token } = useAuth();
  return useQuery({
    queryKey: ["deliverables", pid, runId ?? "latest"],
    enabled: enabled && Boolean(token) && Boolean(pid),
    staleTime: 10 * 1000,
    queryFn: async (): Promise<DeliverablesWithRaw | null> => {
      const [projectRes, runsRes] = await Promise.all([
        api(`/api/projects/${encodeURIComponent(pid)}`),
        api(`/api/runs?project_id=${encodeURIComponent(pid)}`),
      ]);
      const projectData = (await projectRes.json().catch(() => ({}))) as { name?: string };
      const runsData = (await runsRes.json().catch(() => ({}))) as { items?: RunRow[] };
      if (!runsRes.ok) throw new Error(extractApiErrorMessage(runsData, "Failed to load runs"));

      const runs = runsData.items ?? [];
      const run = runId ? runs.find((r) => r.id === runId) : runs[0];
      if (!run) return null; // no runs yet for this engagement — caller shows an empty state

      const [artifactsRes, historyRes, evidenceRes] = await Promise.all([
        api(`/api/runs/${encodeURIComponent(pid)}/${encodeURIComponent(run.id)}/artifacts`),
        api(`/api/runs/${encodeURIComponent(pid)}/${encodeURIComponent(run.id)}/canvas-history`),
        api(`/api/runs/${encodeURIComponent(pid)}/${encodeURIComponent(run.id)}/evidence-claims`),
      ]);
      const artifactsData = (await artifactsRes.json().catch(() => ({}))) as RunArtifactsResponse;
      if (!artifactsRes.ok) throw new Error(extractApiErrorMessage(artifactsData, "Failed to load artifacts"));
      const historyData = (await historyRes.json().catch(() => ({}))) as CanvasHistoryResponse;
      const evidenceData = (await evidenceRes.json().catch(() => ({}))) as {
        claims?: Array<Record<string, unknown>>;
        summary?: Record<string, number>;
      };

      const bag = artifactsData.artifacts ?? {};
      const slides = Array.isArray(bag.pptx_slides) ? bag.pptx_slides : [];
      const hasPptx = slides.length > 0;
      const narrative = bag.narrative_md || bag.sop_markdown || "";
      const hasDocx = Boolean(narrative) || Boolean(bag.docx_base64);
      const claims = (evidenceData.claims ?? []) as RawEvidenceClaim[];
      const claimsCount = claims.length;
      const status = statusFromQuality(bag.quality_status);

      // slide_index from evidence_claims.py is 1-based; group into the
      // slide's own evidence links so SlideEvidencePanel reflects whichever
      // slide is currently selected, not just the first one.
      const claimsBySlideIndex: Record<number, SlideEvidenceLink[]> = {};
      claims.forEach((claim, i) => {
        const slideIdx = (claim.slide_index ?? 1) - 1;
        const bucket = claimsBySlideIndex[slideIdx] ?? (claimsBySlideIndex[slideIdx] = []);
        bucket.push({
          id: claim.id ?? `claim-${i}`,
          index: bucket.length + 1,
          label: claim.claim ?? "Untitled claim",
          description: claim.citation ? `Source: ${claim.citation}` : claim.claim_type ?? "Unverified claim",
          icon: claim.citation ? "library" : "doc",
          verified: claim.status === "grounded",
        });
      });

      const files: EngagementFile[] = [];
      if (hasPptx) {
        files.push({ id: "pptx", type: "pptx", name: "Deliverable deck", meta: `${slides.length} slides`, status });
      }
      if (hasDocx) {
        files.push({ id: "docx", type: "docx", name: "Deliverable document", meta: "Narrative draft", status });
      }
      if (claimsCount) {
        files.push({ id: "evidence", type: "evidence", name: "Evidence register", meta: `${claimsCount} sources` });
      }

      const versions: VersionHistoryEntry[] = (historyData.items ?? []).map((item) => ({
        id: item.id,
        version: item.version,
        current: item.current,
        meta: item.meta,
      }));

      const slideList: Slide[] = slides.map((slide, i) => ({
        id: `slide-${i}`,
        index: i + 1,
        title: slide.title || `Slide ${i + 1}`,
      }));

      const sourcesSummary = claimsCount
        ? `${claimsCount} evidence claim${claimsCount === 1 ? "" : "s"} tracked for this run`
        : "No evidence claims recorded for this run.";

      const activeSlideIndex = 0;
      const engagementName = projectData.name || pid;
      const slideBreadcrumb = engagementName.toUpperCase();
      const slideFooterMeta = `AI-assisted draft · Internal · ${run.status}`;

      return {
        engagementId: pid,
        runId: run.id,
        engagementName,
        title: "Deliverables & artifacts",
        subtitle: "Review the actual output, trace its sources and export the approved version—not just the conversation.",
        tabCounts: { all: files.length, powerpoint: hasPptx ? 1 : 0, word: hasDocx ? 1 : 0, evidenceRegister: claimsCount ? 1 : 0 },
        files,
        versions,
        rawSlides: slides,
        slideBreadcrumb,
        slideSourcesSummary: sourcesSummary,
        slideFooterMeta,
        claimsBySlideIndex,
        pptx: {
          name: "Deliverable deck",
          versionLabel: `PPTX · ${versions[0]?.version ?? "v0.1"}`,
          status,
          slides: slideList,
          activeSlideIndex,
          slideDetail: toSlideDetail(
            slides[activeSlideIndex],
            activeSlideIndex,
            slides.length,
            slideBreadcrumb,
            sourcesSummary,
            slideFooterMeta
          ),
          evidenceLinks: claimsBySlideIndex[activeSlideIndex] ?? [],
        },
        docx: {
          name: "Deliverable document",
          status,
          versionLabel: versions[0]?.version ?? "v0.1",
          preview: {
            breadcrumb: `${engagementName.toUpperCase()} / NARRATIVE`,
            title: "Deliverable document",
            meta: `Run ${run.id} · ${run.status}`,
            sections: narrative
              ? splitMarkdownSections(narrative)
              : [{ heading: "Preview not available", body: "Download the document to read it." }],
            footerMeta: "Internal · Human review required",
            pageLabel: "",
          },
          citationSummary: `${claimsCount} source citation${claimsCount === 1 ? "" : "s"}`,
          exportWarning: null,
          generatedFootnote: `Generated for run ${run.id}.`,
        },
      };
    },
  });
}
