"use client";

import { useQuery } from "@tanstack/react-query";

import type { AdminReviewsGovernanceDetail } from "@/types/api";

// Static mock matching the "Review operations & governance" screenshot.
const MOCK_ADMIN_REVIEWS: AdminReviewsGovernanceDetail = {
  tabCounts: { reviewQueue: 12, riskRegister: 3, policies: 8 },
  queue: [
    { id: "rv-104", itemReference: "Northstar roadmap · RV-104", reviewer: "Priya Shah", type: "PPTX v0.8", state: "Changes requested" },
    { id: "lp-041", itemReference: "Benefits toolkit · LP-041", reviewer: "Priya Shah", type: "Practice v2.1", state: "Attribution gap" },
    { id: "sk-008", itemReference: "Roadmap builder · SK-008", reviewer: "Priya Shah", type: "Skill v2.2", state: "Test failed" },
    { id: "ar-019", itemReference: "Atlas access request · AR-019", reviewer: "Jordan Kim", type: "Source access", state: "Blocked · High risk" },
  ],
  selectedReview: {
    id: "rv-104",
    code: "RV-104",
    title: "Northstar transformation roadmap",
    riskLevel: "Medium risk",
    badges: ["Changes requested", "Export locked"],
    artifactOwner: "PPTX v0.8 · Alex Chen",
    assignedApprover: "Priya Shah · Due 12 Oct",
    riskDescription:
      "Risk: one benefits assumption lacks supporting evidence. A second comment requests a named pilot owner. Both must be addressed before approval.",
    warning: {
      title: "Approval is version-specific",
      description: "22 of 23 claims are cited. Approval cannot carry over from a prior version or be granted by the artifact author.",
    },
    footnote: "Your role: administrator. Approval decisions are restricted to the assigned independent reviewer.",
  },
  policyControls: [
    { id: "pc-1", label: "Human approval before export", state: "Enforced" },
    { id: "pc-2", label: "Source-permission inheritance", state: "Enforced" },
    { id: "pc-3", label: "Assumption & citation checks", state: "Enforced" },
    { id: "pc-4", label: "180-day default retention", state: "Active" },
  ],
  policyCode: "POL-2026.10",
  exportPermissionsNote:
    "Approved PPTX / DOCX only · Engagement leads may download · Restricted content requires a data-owner approval · External sharing is not permitted.",
  roleAccess: [
    { id: "ra-contributor", role: "Contributor", allowed: "Draft & cite", restricted: "Approve / export" },
    { id: "ra-lead", role: "Lead", allowed: "Submit & download", restricted: "Self-approval" },
    { id: "ra-reviewer", role: "Reviewer", allowed: "Approve assigned", restricted: "Edit source rights" },
    { id: "ra-admin", role: "Admin", allowed: "Manage & audit", restricted: "Bypass review" },
  ],
  auditTrail: [
    { id: "at-1", title: "Evidence check", attribution: "System · RV-104 · 1 unsupported claim flagged", icon: "check" },
    { id: "at-2", title: "Version created", attribution: "Alex Chen · Northstar PPTX v0.8 · Draft", icon: "history" },
    { id: "at-3", title: "Skill submitted", attribution: "Maya Patel · Roadmap builder v2.2", icon: "send" },
    { id: "at-4", title: "Changes requested", attribution: "Priya Shah · RV-104 · 2 open comments", icon: "comment" },
  ],
};

export function useAdminReviewsGovernanceQuery(enabled = true) {
  return useQuery({
    queryKey: ["admin-reviews-governance"],
    enabled,
    staleTime: 5 * 60 * 1000,
    queryFn: async (): Promise<AdminReviewsGovernanceDetail> => MOCK_ADMIN_REVIEWS,
  });
}
