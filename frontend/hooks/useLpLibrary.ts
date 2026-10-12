"use client";

import { useQuery } from "@tanstack/react-query";

import type { LPLibraryDetail } from "@/types/api";

// Static mock matching the "Leading Practice Library" screenshot — same
// preview pattern as useEngagements.ts / useDeliverables.ts.
const MOCK_LP_LIBRARY: LPLibraryDetail = {
  totalPractices: 128,
  categories: [
    { id: "all", label: "All practices", count: 128 },
    { id: "transformation", label: "Transformation", count: 42 },
    { id: "operating-model", label: "Operating model", count: 16 },
    { id: "governance", label: "Governance", count: 14 },
    { id: "change-adoption", label: "Change & adoption", count: 12 },
    { id: "finance", label: "Finance", count: 24 },
    { id: "technology", label: "Technology", count: 31 },
    { id: "people-workforce", label: "People & workforce", count: 19 },
    { id: "risk-controls", label: "Risk & controls", count: 12 },
  ],
  activeCategoryId: "operating-model",
  matchingCount: 4,
  cards: [
    {
      id: "lp-016",
      title: "Operating model playbook",
      description: "Service ownership, decision rights and phased transition.",
      status: "Approved",
      maturity: "Managed",
      category: "Transformation",
      versionLabel: "v3.2 · Maya Patel · 06 Oct 2026",
    },
    {
      id: "lp-021",
      title: "Transformation governance guide",
      description: "Stage gates, risk escalation and accountable sponsors.",
      status: "Approved",
      maturity: "Optimized",
      category: "Transformation",
      versionLabel: "v2.4 · Priya Shah · 30 Sep 2026",
    },
    {
      id: "lp-033",
      title: "Service ownership framework",
      description: "RACI patterns and cross-functional handoff design.",
      status: "Approved",
      maturity: "Managed",
      category: "Transformation",
      versionLabel: "v1.8 · Sam Rivera · 25 Sep 2026",
    },
    {
      id: "lp-040",
      title: "Benefits realization toolkit",
      description: "Baseline measures, benefits registers and validation.",
      status: "Approved",
      maturity: "Defined",
      category: "Transformation",
      versionLabel: "v2.0 · Maya Patel · 22 Sep 2026",
    },
  ],
  practices: {
    "lp-016": {
      id: "lp-016",
      code: "LP-016",
      title: "Operating model playbook",
      description:
        "A structured method for translating strategy into service ownership, decision rights and an executable transition plan.",
      status: "Approved",
      versionLabel: "v3.2",
      maturity: "Managed maturity",
      recommendedWhen:
        "Accountabilities are fragmented, cross-functional handoffs are unclear, or a new service model needs a sequenced rollout.",
      coreGuidance: [
        "Define service boundaries and accountable owners.",
        "Agree decision rights before redesigning processes.",
        "Validate the model through a 90-day pilot.",
        "Scale only after stage-gate evidence is reviewed.",
      ],
      sourceAttribution: "Advisory Methods team",
      practiceOwner: "Maya Patel",
      approvedMeta: "06 Oct 2026 · Priya Shah",
      sourceQuality: "Verified · 8 references",
    },
  },
};

export function useLpLibraryQuery(enabled = true) {
  return useQuery({
    queryKey: ["lp-library"],
    enabled,
    staleTime: 5 * 60 * 1000,
    queryFn: async (): Promise<LPLibraryDetail> => MOCK_LP_LIBRARY,
  });
}
