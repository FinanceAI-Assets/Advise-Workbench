/**
 * Adapters turning real run-artifact JSON (pptx_slides.json entries,
 * narrative_md/sop_markdown) into the mock-era presentational shapes
 * (SlideDetail, DocSection[]) that SlideCanvas / WordArtifactPanel already
 * render. Lossy-but-functional per the integration plan: these do not
 * reproduce the mock's bespoke 3-phase roadmap concept, they just surface
 * the artifact's own content inside the same visual slots.
 */

import type { DocSection, SlidePhase, SlideDetail } from "@/types/api";

// One entry of artifacts.pptx_slides — field names confirmed against
// src/deliverables/pptx/deliverable_pptx.py's per-slide-type renderers.
export type RawPptxSlide = {
  title?: string;
  slide_type?: string;
  bullets?: string[];
  stat_cards?: Array<{ stat?: string; label?: string; description?: string }>;
  column_cards?: Array<{ heading?: string; body?: string }>;
  stack_layers?: Array<{ label?: string; description?: string }>;
  table?: { headers?: string[]; rows?: string[][] };
  [key: string]: unknown;
};

function phasesFromSlide(slide: RawPptxSlide): SlidePhase[] {
  const type = slide.slide_type ?? "";
  if (type === "bullets" && Array.isArray(slide.bullets)) {
    return slide.bullets.slice(0, 6).map((text, i) => ({
      label: `Point ${i + 1}`,
      title: "",
      description: text,
    }));
  }
  if (type === "stat_cards" && Array.isArray(slide.stat_cards)) {
    return slide.stat_cards.map((card) => ({
      label: card.label ?? "",
      title: card.stat ?? "",
      description: card.description ?? "",
    }));
  }
  if (type === "column_cards" && Array.isArray(slide.column_cards)) {
    return slide.column_cards.map((card) => ({
      label: "",
      title: card.heading ?? "",
      description: card.body ?? "",
    }));
  }
  if (type === "stack_layers" && Array.isArray(slide.stack_layers)) {
    return slide.stack_layers.map((layer) => ({
      label: "",
      title: layer.label ?? "",
      description: layer.description ?? "",
    }));
  }
  if (type === "table" && slide.table) {
    const headers = slide.table.headers ?? [];
    const rows = slide.table.rows ?? [];
    const headerPhase: SlidePhase = { label: "Columns", title: headers.join(" · "), description: "" };
    const rowPhases = rows.slice(0, 5).map((row, i) => ({
      label: `Row ${i + 1}`,
      title: "",
      description: row.join(" · "),
    }));
    return [headerPhase, ...rowPhases];
  }
  return [];
}

/** Convert one raw pptx_slides.json entry into the SlideDetail shape SlideCanvas renders. */
export function toSlideDetail(
  slide: RawPptxSlide | undefined,
  index: number,
  total: number,
  breadcrumb: string,
  sourcesSummary: string,
  footerMeta: string
): SlideDetail {
  if (!slide) {
    return {
      breadcrumb,
      headline: "No slide content",
      phases: [],
      sources: sourcesSummary,
      footerMeta,
      pageLabel: `${String(index + 1).padStart(2, "0")} / ${Math.max(total, 1)}`,
    };
  }
  return {
    breadcrumb,
    headline: slide.title || `Slide ${index + 1}`,
    phases: phasesFromSlide(slide),
    sources: sourcesSummary,
    footerMeta,
    pageLabel: `${String(index + 1).padStart(2, "0")} / ${Math.max(total, 1)}`,
  };
}

/** Split a markdown document on `#`/`##` headings into WordArtifactPanel's DocSection[]. */
export function splitMarkdownSections(markdown: string): DocSection[] {
  const text = (markdown || "").trim();
  if (!text) return [];
  const lines = text.split("\n");
  const sections: DocSection[] = [];
  let currentHeading = "";
  let currentBody: string[] = [];

  const flush = () => {
    const body = currentBody.join("\n").trim();
    if (currentHeading || body) {
      sections.push({ heading: currentHeading || "Overview", body });
    }
  };

  for (const line of lines) {
    const match = /^(#{1,3})\s+(.*)$/.exec(line);
    if (match) {
      flush();
      currentHeading = match[2].trim();
      currentBody = [];
    } else {
      currentBody.push(line);
    }
  }
  flush();
  return sections.length ? sections : [{ heading: "Overview", body: text }];
}
