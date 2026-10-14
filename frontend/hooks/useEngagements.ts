"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { useAuth } from "@/lib/auth-context";
import { fetchJson } from "@/lib/workbenchApi";
import type {
  ActivityItem,
  EngagementDetail,
  EngagementStat,
  EngagementsPage,
  ExportReadiness,
  NextActionBuckets,
  TeamMember,
} from "@/types/api";

// Hooks for the engagements screens. Each one reads a view model from
// src/app/api/engagements.py, so a screen needs a single request.

export type EngagementListFilters = { q: string; status: "active" | "all" | "archived"; mine: boolean; page: number };

export const ENGAGEMENTS_PAGE_SIZE = 5;

export function useEngagementsQuery(filters: EngagementListFilters, enabled = true) {
  const { api, token } = useAuth();
  return useQuery({
    queryKey: ["engagements", filters],
    enabled: enabled && Boolean(token),
    staleTime: 30 * 1000,
    placeholderData: (previous) => previous,
    queryFn: () => {
      const params = new URLSearchParams({
        q: filters.q,
        status: filters.status,
        mine: String(filters.mine),
        page: String(filters.page),
        page_size: String(ENGAGEMENTS_PAGE_SIZE),
      });
      return fetchJson<EngagementsPage>(api, `/api/engagements?${params}`, "Failed to load engagements");
    },
  });
}

export function useEngagementStatsQuery(enabled = true) {
  const { api, token } = useAuth();
  return useQuery({
    queryKey: ["engagement-stats"],
    enabled: enabled && Boolean(token),
    staleTime: 60 * 1000,
    queryFn: async () =>
      (await fetchJson<{ items: EngagementStat[] }>(api, "/api/engagements/stats", "Failed to load engagement stats"))
        .items,
  });
}

export function useNextActionsQuery(enabled = true) {
  const { api, token } = useAuth();
  return useQuery({
    queryKey: ["engagement-next-actions"],
    enabled: enabled && Boolean(token),
    staleTime: 60 * 1000,
    queryFn: () => fetchJson<NextActionBuckets>(api, "/api/engagements/next-actions", "Failed to load next actions"),
  });
}

export function useRecentActivityQuery(enabled = true) {
  const { api, token } = useAuth();
  return useQuery({
    queryKey: ["engagement-recent-activity"],
    enabled: enabled && Boolean(token),
    staleTime: 60 * 1000,
    queryFn: async () =>
      (await fetchJson<{ items: ActivityItem[] }>(api, "/api/engagements/activity?limit=5", "Failed to load activity"))
        .items,
  });
}

export function useEngagementDetailQuery(id: string, enabled = true) {
  const { api, token } = useAuth();
  return useQuery({
    queryKey: ["engagement", id],
    enabled: enabled && Boolean(token) && Boolean(id),
    staleTime: 30 * 1000,
    queryFn: () =>
      fetchJson<EngagementDetail>(api, `/api/engagements/${encodeURIComponent(id)}`, `Engagement "${id}" not found`),
  });
}

export function useEngagementActivityQuery(id: string, enabled = true) {
  const { api, token } = useAuth();
  return useQuery({
    queryKey: ["engagement", id, "activity"],
    enabled: enabled && Boolean(token) && Boolean(id),
    queryFn: async () =>
      (
        await fetchJson<{ items: ActivityItem[] }>(
          api,
          `/api/engagements/${encodeURIComponent(id)}/activity`,
          "Failed to load activity"
        )
      ).items,
  });
}

export function useExportReadinessQuery(id: string, enabled = true) {
  const { api, token } = useAuth();
  return useQuery({
    queryKey: ["engagement", id, "export"],
    enabled: enabled && Boolean(token) && Boolean(id),
    queryFn: () =>
      fetchJson<ExportReadiness>(
        api,
        `/api/engagements/${encodeURIComponent(id)}/export-readiness`,
        "Failed to load export readiness"
      ),
  });
}

export type EngagementInput = {
  name?: string;
  clientOrg?: string;
  type?: string;
  brief?: string;
  sponsorObjective?: string;
  scope?: string;
  successMeasures?: string;
  startDate?: string;
  targetClose?: string;
  classification?: string;
  stage?: string;
};

export function useCreateEngagementMutation() {
  const { api } = useAuth();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: EngagementInput) =>
      fetchJson<{ id: string }>(api, "/api/engagements", "Could not create the engagement", {
        method: "POST",
        body: JSON.stringify(body),
      }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["engagements"] });
      void qc.invalidateQueries({ queryKey: ["engagement-stats"] });
    },
  });
}

export function useUpdateEngagementMutation(id: string) {
  const { api } = useAuth();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: EngagementInput) =>
      fetchJson<{ id: string }>(api, `/api/engagements/${encodeURIComponent(id)}`, "Could not save the engagement", {
        method: "PUT",
        body: JSON.stringify(body),
      }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["engagement", id] });
      void qc.invalidateQueries({ queryKey: ["engagements"] });
    },
  });
}

type MemberChange =
  | { action: "add"; email: string; role: string }
  | { action: "role"; memberId: string; role: string }
  | { action: "remove"; memberId: string };

export function useMemberMutation(id: string) {
  const { api } = useAuth();
  const qc = useQueryClient();
  const base = `/api/engagements/${encodeURIComponent(id)}/members`;
  return useMutation({
    mutationFn: (change: MemberChange) => {
      if (change.action === "add") {
        return fetchJson(api, base, "Could not add the member", {
          method: "POST",
          body: JSON.stringify({ email: change.email, role: change.role }),
        });
      }
      const path = `${base}/${encodeURIComponent(change.memberId)}`;
      if (change.action === "role") {
        return fetchJson(api, path, "Could not change the role", {
          method: "PATCH",
          body: JSON.stringify({ role: change.role }),
        });
      }
      return fetchJson(api, path, "Could not remove the member", { method: "DELETE" });
    },
    onSuccess: () => void qc.invalidateQueries({ queryKey: ["engagement", id] }),
  });
}

export const MEMBER_ROLES = ["Engagement lead", "Independent reviewer", "Contributor", "Practice advisor", "Viewer"];

export type { TeamMember };
