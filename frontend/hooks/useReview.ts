"use client";

import { useQuery } from "@tanstack/react-query";

import type { ReviewDetail } from "@/types/api";

// Static mock matching the "Review: Transformation roadmap" screenshot.
const MOCK_REVIEW: ReviewDetail = {
  id: "rv-104",
  code: "RV-104",
  engagementName: "Northstar transformation",
  artifactName: "Transformation roadmap",
  versionLabel: "PPTX v0.8",
  owner: "Alex Chen",
  reviewer: "Priya Shah",
  dueDate: "12 Oct 2026",
  steps: [
    { id: "brief", index: 1, label: "Brief", status: "complete", helper: "Complete" },
    { id: "sources", index: 2, label: "Sources", status: "complete", helper: "Complete" },
    { id: "draft", index: 3, label: "Draft", status: "complete", helper: "Complete" },
    { id: "review", index: 4, label: "Review", status: "in-progress", helper: "In progress" },
    { id: "export", index: 5, label: "Export", status: "upcoming", helper: "Upcoming" },
  ],
  slide: {
    breadcrumb: "NORTHSTAR / TRANSFORMATION",
    headline: "A phased roadmap to a resilient operating model",
    phases: [
      { label: "01 / 0–30 days", title: "Align", description: "Baseline processes and agree decision rights." },
      { label: "02 / 31–60 days", title: "Design", description: "Pilot service ownership and test controls." },
      { label: "03 / 61–90 days", title: "Scale", description: "Measure outcomes and embed governance." },
    ],
    sources: "Sources: [1] Operating model playbook v3.2, §4 · [2] Northstar discovery notes, p.8",
    footerMeta: "AI-assisted draft · Internal · v0.8",
    pageLabel: "04 / 12",
  },
  slideCommentCount: 2,
  evidenceChecksRunMeta: "Run 08 Oct · 09:45",
  evidenceChecks: [
    {
      id: "citation-coverage",
      check: "Citation coverage · 22 / 23 claims",
      result: "Gap",
      resultLabel: "1 gap",
      action: "Validate benefits assumption",
    },
    {
      id: "source-permissions",
      check: "Source permissions & freshness",
      result: "Passed",
      resultLabel: "Passed",
      action: "18 permitted sources",
    },
    {
      id: "practice-version",
      check: "Practice version & file integrity",
      result: "Passed",
      resultLabel: "Passed",
      action: "Playbook v3.2 · PPTX valid",
    },
  ],
  comments: [
    {
      id: "evidence-gap",
      title: "Evidence gap",
      status: "Open",
      attribution: "Priya Shah · 07 Oct, 16:20 · Slide 4 · Benefits assumptions",
      body: "Keep benefits directional until a baseline is validated. Add a source or mark the statement as an assumption.",
    },
    {
      id: "clarify-accountability",
      title: "Clarify accountability",
      status: "Open",
      attribution: "Priya Shah · 07 Oct, 16:24 · Slide 4 · Phase 2 ownership",
      body: "Name an accountable service owner for the pilot stage gate. The team name alone is not enough.",
    },
  ],
  openCount: 2,
  resolvedCount: 1,
  approverName: "Priya Shah",
  approverRole: "Engagement reviewer",
  approvalStatus: "Awaiting revision",
  approvalTimeline: [
    { id: "submitted-v07", title: "Submitted v0.7", attribution: "Alex Chen · 07 Oct, 14:12", icon: "check" },
    { id: "changes-requested", title: "Changes requested", attribution: "Priya Shah · 07 Oct, 16:24 · 2 open items", icon: "comment" },
    { id: "revision-v08", title: "Revision v0.8 prepared", attribution: "Alex Chen · 08 Oct, 09:42 · Not resubmitted", icon: "edit" },
  ],
};

export function useReviewQuery(enabled = true) {
  return useQuery({
    queryKey: ["review", "rv-104"],
    enabled,
    staleTime: 5 * 60 * 1000,
    queryFn: async (): Promise<ReviewDetail> => MOCK_REVIEW,
  });
}
