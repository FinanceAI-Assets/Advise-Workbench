"use client";

import { useQuery } from "@tanstack/react-query";

import type { AdminOverviewDetail } from "@/types/api";

// Static mock matching the "Platform overview" screenshot.
const MOCK_OVERVIEW: AdminOverviewDetail = {
  stats: [
    { id: "active-engagements", label: "Active engagements", value: "24", helper: "8 in your advisory portfolio" },
    {
      id: "pending-approvals",
      label: "Pending approvals",
      value: "12",
      helper: "5 deliverables · 4 practices · 3 skills",
      helperTone: "warning",
    },
    {
      id: "indexing-success",
      label: "Indexing success",
      value: "99.2%",
      helper: "248 / 250 documents · Last 24 hours",
      helperTone: "success",
    },
    { id: "open-risks", label: "Open governance risks", value: "3", helper: "1 high · 2 medium · No critical" },
  ],
  pendingApprovals: [
    { id: "pa-1", item: "Benefits realization toolkit", typeVersion: "Practice · v2.1", assignedTo: "Priya Shah", due: "09 Oct", state: "Quality review" },
    { id: "pa-2", item: "Roadmap builder", typeVersion: "Skill · v2.2", assignedTo: "Priya Shah", due: "09 Oct", state: "Approval" },
    { id: "pa-3", item: "Meridian executive memo", typeVersion: "DOCX · v1.2", assignedTo: "Priya Shah", due: "09 Oct", state: "In review" },
    { id: "pa-4", item: "Northstar roadmap", typeVersion: "PPTX · v0.8", assignedTo: "Priya Shah", due: "12 Oct", state: "Changes requested" },
  ],
  pendingApprovalsTotal: 12,
  ingestionHealth: [
    { id: "ih-1", title: "Library repository", meta: "Last sync 09:30 · 128 practices indexed", status: "Healthy", icon: "library" },
    { id: "ih-2", title: "Engagement uploads", meta: "Last sync 09:42 · 120 documents indexed", status: "Healthy", icon: "upload" },
    { id: "ih-3", title: "Policy knowledge connector", meta: "2 documents failed · Text extraction error", status: "Attention", icon: "plug" },
  ],
  ingestionUpdatedMeta: "Updated 09:48",
  ingestionWarning: {
    title: "2 files need intervention",
    description: "Scanned policy PDFs need OCR before indexing. Existing approved sources remain available.",
  },
  riskQueue: [
    { id: "rq-1", riskScope: "Atlas restricted-source request", severity: "High", owner: "Jordan Kim", control: "Access request blocked" },
    { id: "rq-2", riskScope: "Northstar unsupported benefits", severity: "Medium", owner: "Alex Chen", control: "Export locked · RV-104" },
  ],
  riskQueueOpenCount: 3,
  riskQueueFootnote: "1 additional medium risk: retention exception awaiting owner confirmation.",
  controlsAudit: [
    { id: "ca-1", label: "Human approval before export", state: "Enforced" },
    { id: "ca-2", label: "Permission-aware retrieval", state: "Enforced" },
  ],
  controlsAuditEvent: "Latest audit event: Roadmap builder v2.2 submitted for approval by Maya Patel at 09:18.",
};

export function useAdminOverviewQuery(enabled = true) {
  return useQuery({
    queryKey: ["admin-overview"],
    enabled,
    staleTime: 5 * 60 * 1000,
    queryFn: async (): Promise<AdminOverviewDetail> => MOCK_OVERVIEW,
  });
}
