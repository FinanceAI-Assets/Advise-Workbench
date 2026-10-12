"use client";

import { useQuery } from "@tanstack/react-query";

import type { SkillsDetail } from "@/types/api";

// Static mock matching the "Expert workflows, repeatable outputs" screenshot.
const MOCK_SKILLS: SkillsDetail = {
  totalPublished: 6,
  cards: [
    {
      id: "sk-008",
      name: "Roadmap builder",
      description: "Turn a grounded brief into phased actions, owners and stage gates.",
      versionLabel: "v2.1",
      formats: "PPTX + DOCX",
      published: true,
    },
    {
      id: "sk-011",
      name: "Discovery synthesis",
      description: "Synthesize interviews and documents into themes and implications.",
      versionLabel: "v1.6",
      formats: "DOCX",
      published: true,
    },
    {
      id: "sk-014",
      name: "Operating model advisor",
      description: "Explore service boundaries, accountabilities and design principles.",
      versionLabel: "v3.0",
      formats: "PPTX + DOCX",
      published: true,
    },
    {
      id: "sk-017",
      name: "Governance designer",
      description: "Structure decision rights, escalation paths and review cadences.",
      versionLabel: "v1.4",
      formats: "PPTX",
      published: true,
    },
    {
      id: "sk-019",
      name: "Evidence checker",
      description: "Check claims, citations and assumptions before human review.",
      versionLabel: "v2.2",
      formats: "DOCX",
      published: true,
    },
    {
      id: "sk-022",
      name: "Executive storyteller",
      description: "Refine the narrative for a concise, credible leadership discussion.",
      versionLabel: "v1.9",
      formats: "PPTX",
      published: true,
    },
  ],
  skills: {
    "sk-008": {
      id: "sk-008",
      code: "SK-008",
      name: "Roadmap builder",
      versionLabel: "v2.1",
      category: "Transformation",
      evidenceRequired: true,
      description:
        "A structured advisory workflow for a phased transformation plan. Available to engagement leads and contributors.",
      howItWorks: [
        "Confirm the objective, scope, timeline and sponsor.",
        "Retrieve approved practices and engagement evidence.",
        "Propose phased actions, owners and measurable gates.",
        "Label assumptions and unsupported benefits explicitly.",
        "Produce source-linked drafts for human review.",
      ],
      requiredInputs: "Brief · Discovery notes · Time horizon",
      expectedOutputs: "12-slide PPTX · 6-page DOCX",
      evidencePolicy:
        "Every substantive claim needs a cited source. Use only permitted, indexed sources. Stop and flag evidence gaps; never invent quantitative benefits.",
      maintainedBy: "Maya Patel · Advisory Methods",
      lastPublished: "06 Oct 2026 · Approved by Priya Shah",
      runInEngagement: "Northstar transformation · NS-042",
    },
  },
};

export function useSkillsCatalogQuery(enabled = true) {
  return useQuery({
    queryKey: ["skills-catalog"],
    enabled,
    staleTime: 5 * 60 * 1000,
    queryFn: async (): Promise<SkillsDetail> => MOCK_SKILLS,
  });
}
