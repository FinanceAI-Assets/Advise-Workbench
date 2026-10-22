"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { useAuth } from "@/lib/auth-context";
import { fetchJson } from "@/lib/workbenchApi";
import type {
  AdminEngagementsDetail,
  AdminLibraryDetail,
  AdminOverviewDetail,
  AdminReviewsGovernanceDetail,
  AdminSkillsManagementDetail,
  AuditTrailEvent,
  RiskQueueRow,
  SelectedEngagementDetail,
  SelectedReviewGovernanceDetail,
} from "@/types/api";

// Admin console data. Every endpoint is under /api/admin and requires an administrator.

export type AdminRecord = { id: string } & Record<string, string>;

export type AdminOverview = AdminOverviewDetail & { ingestionJobs: AdminRecord[] };

export type AdminEngagements = Omit<AdminEngagementsDetail, "selected"> & {
  selected: (SelectedEngagementDetail & { retentionDays: number; status: string; archiveReady: boolean }) | null;
  deliverables: AdminRecord[];
  retentionExceptions: AdminRecord[];
  exportRequests: AdminRecord[];
  roles: string[];
};

export type AdminLibrary = AdminLibraryDetail & { ingestionJobs: AdminRecord[] };

export type AdminReviews = Omit<AdminReviewsGovernanceDetail, "selectedReview"> & {
  selectedReview: (SelectedReviewGovernanceDetail & { reviewerId: string | null; ownerId: string | null }) | null;
  risks: RiskQueueRow[];
  fullAuditTrail: AuditTrailEvent[];
  reviewers: Array<{ id: string; name: string }>;
};

function useAdminQuery<T>(key: unknown[], path: string) {
  const { api, token, user } = useAuth();
  return useQuery({
    queryKey: ["admin", ...key],
    enabled: Boolean(token) && Boolean(user),
    staleTime: 15 * 1000,
    queryFn: () => fetchJson<T>(api, path, "Failed to load the admin console"),
  });
}

export const useAdminOverviewQuery = () => useAdminQuery<AdminOverview>(["overview"], "/api/admin/overview");

export const useAdminEngagementsQuery = (q: string, selected: string) =>
  useAdminQuery<AdminEngagements>(
    ["engagements", q, selected],
    `/api/admin/engagements?q=${encodeURIComponent(q)}&selected=${encodeURIComponent(selected)}`
  );

export const useAdminLibraryQuery = () => useAdminQuery<AdminLibrary>(["library"], "/api/admin/library");

export const useAdminSkillsQuery = () => useAdminQuery<AdminSkillsManagementDetail>(["skills"], "/api/admin/skills");

export const useAdminReviewsQuery = (selected: string) =>
  useAdminQuery<AdminReviews>(["reviews", selected], `/api/admin/reviews?selected=${encodeURIComponent(selected)}`);

/** One administrative change. `path` is relative to /api/admin; every change refreshes the console. */
export type AdminAction = { path: string; method?: "POST" | "PUT"; body: Record<string, unknown> };

export function useAdminAction() {
  const { api } = useAuth();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (action: AdminAction) =>
      fetchJson(api, `/api/admin${action.path}`, "The change could not be saved", {
        method: action.method ?? "POST",
        body: JSON.stringify(action.body),
      }),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ["admin"] }),
  });
}
