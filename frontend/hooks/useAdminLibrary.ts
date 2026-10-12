"use client";

import { useQuery } from "@tanstack/react-query";

import type { AdminLibraryDetail } from "@/types/api";

// Static mock matching the "Library management" screenshot.
const MOCK_ADMIN_LIBRARY: AdminLibraryDetail = {
  pipelineSteps: [
    { id: "source-upload", index: 1, label: "Source upload", status: "complete", helper: "Complete" },
    { id: "extract-chunk", index: 2, label: "Extract & chunk", status: "complete", helper: "Complete" },
    { id: "index-validate", index: 3, label: "Index & validate", status: "complete", helper: "Complete" },
    { id: "quality-review", index: 4, label: "Quality review", status: "in-progress", helper: "Current", icon: "cycle" },
    { id: "approve-publish", index: 5, label: "Approve & publish", status: "upcoming", helper: "Pending" },
  ],
  practiceInventoryTotal: "128 approved · 4 pending",
  practiceInventory: [
    { id: "pi-1", practiceSource: "Operating model playbook", version: "v3.2", indexing: "Indexed", lifecycle: "Published" },
    { id: "pi-2", practiceSource: "Transformation governance guide", version: "v2.4", indexing: "Indexed", lifecycle: "Published" },
    { id: "pi-3", practiceSource: "Benefits realization toolkit", version: "v2.1 candidate", indexing: "Indexed", lifecycle: "Quality review" },
    { id: "pi-4", practiceSource: "Policy handbook scanned.pdf", version: "New source", indexing: "OCR failed", lifecycle: "Not eligible" },
  ],
  latestIngestionJob: {
    id: "job-208",
    filename: "benefits-realization-toolkit-v2.1.docx",
    meta: "1.8 MB · Uploaded by Maya Patel · Internal methods content",
    status: "Indexed",
    extractionMeta: "42 pages · 86 chunks",
    indexValidationMeta: "86 / 86 embedded · No duplicates",
    provenanceMeta: "Source hash & uploader recorded",
    warning: {
      title: "Connector exception: scanned policy files",
      description: "Policy handbook and Control appendix require OCR. Retry after a readable source is supplied; neither is in retrieval scope.",
    },
  },
  qualityReview: {
    id: "lp-041",
    code: "LP-041",
    title: "Benefits realization toolkit",
    versionLabel: "v2.1 candidate",
    approvalState: "Approval blocked",
    taxonomy: "Transformation / Benefits",
    maturity: "Defined",
    practiceOwner: "Maya Patel",
    approver: "Priya Shah",
    sourceQualityChecks: [
      { id: "sq-1", label: "Provenance and ownership", state: "Passed" },
      { id: "sq-2", label: "Citation verification", state: "7 / 8 verified" },
      { id: "sq-3", label: "Duplicate & classification scan", state: "Passed" },
    ],
    warning: {
      title: "Reference 8 needs attribution",
      description: "Replace the uncited benchmark with a verified source or remove it before approval.",
    },
    footnote: "Published v2.0 remains available to users. Approving v2.1 creates a new immutable release with a full audit record.",
  },
};

export function useAdminLibraryQuery(enabled = true) {
  return useQuery({
    queryKey: ["admin-library"],
    enabled,
    staleTime: 5 * 60 * 1000,
    queryFn: async (): Promise<AdminLibraryDetail> => MOCK_ADMIN_LIBRARY,
  });
}
