"use client";

import { useQuery } from "@tanstack/react-query";

import { extractApiErrorMessage } from "@/lib/api-error";
import { useAuth } from "@/lib/auth-context";
import type {
  ActivityItem,
  EngagementDetail,
  EngagementRow,
  EngagementStage,
  EngagementStat,
  EngagementStep,
  EvidenceSource,
  NextAction,
  ProjectRow,
  TeamMember,
} from "@/types/api";

// Real-backend hooks, same filenames/signatures as the mock version they
// replace so every caller (EngagementsPage, EngagementDetailPage) keeps
// working unmodified. Backed by src/app/api/projects/crud.py (list/get) and
// the additive src/app/api/projects/engagement_meta.py routes.

type Api = ReturnType<typeof useAuth>["api"];

// Raw shape of GET/PUT /api/projects/{pid}/engagement-meta — see
// src/app/api/projects/engagement_meta.py:_engagement_meta_response. Never
// 404s: a project with no row yet gets sensible defaults from the backend.
type EngagementMetaResponse = {
  project_id: string;
  code: string;
  type: string;
  stage: string;
  progress: number;
  next_task: string;
  due_date: string;
};

const STAGE_VALUES: EngagementStage[] = ["Brief", "Sources", "Drafting", "In review", "Approved"];

// EngagementMeta.stage is an unconstrained string server-side; coerce any
// unexpected/legacy value into the literal union EngagementStageBadge styles.
function coerceStage(raw: string | null | undefined): EngagementStage {
  return (STAGE_VALUES as string[]).includes(raw ?? "") ? (raw as EngagementStage) : "Brief";
}

const STAGE_INDEX: Record<EngagementStage, number> = {
  Brief: 0,
  Sources: 1,
  Drafting: 2,
  "In review": 3,
  Approved: 4,
};

const STEP_DEFS: Array<{ id: string; label: string }> = [
  { id: "brief", label: "Brief" },
  { id: "sources", label: "Sources" },
  { id: "draft", label: "Draft" },
  { id: "review", label: "Review" },
  { id: "export", label: "Export" },
];

function stepsForStage(stage: EngagementStage): EngagementStep[] {
  const current = STAGE_INDEX[stage];
  return STEP_DEFS.map((step, i) => ({
    id: step.id,
    index: i + 1,
    label: step.label,
    status: i < current ? "complete" : i === current ? "in-progress" : "upcoming",
    helper: i < current ? "Complete" : i === current ? "In progress" : "Upcoming",
  }));
}

async function fetchEngagementMeta(api: Api, pid: string): Promise<EngagementMetaResponse> {
  const res = await api(`/api/projects/${encodeURIComponent(pid)}/engagement-meta`);
  const data = (await res.json().catch(() => ({}))) as EngagementMetaResponse;
  if (!res.ok) throw new Error(extractApiErrorMessage(data, "Failed to load engagement metadata"));
  return data;
}

async function fetchMembers(api: Api, pid: string): Promise<TeamMember[]> {
  const res = await api(`/api/projects/${encodeURIComponent(pid)}/members`);
  const data = (await res.json().catch(() => ({}))) as { items?: TeamMember[] };
  if (!res.ok) return [];
  return Array.isArray(data.items) ? data.items : [];
}

function ownerFromMembers(members: TeamMember[]): string {
  const owner = members.find((m) => m.roleAndAccess === "Owner");
  return owner?.name ?? members[0]?.name ?? "—";
}

export function useEngagementsQuery(enabled = true) {
  const { api, token } = useAuth();
  return useQuery({
    queryKey: ["engagements"],
    enabled: enabled && Boolean(token),
    staleTime: 60 * 1000,
    queryFn: async (): Promise<EngagementRow[]> => {
      const res = await api("/api/projects");
      const data = (await res.json().catch(() => ({}))) as { items?: ProjectRow[] };
      if (!res.ok) throw new Error(extractApiErrorMessage(data, "Failed to load engagements"));
      const projects = data.items ?? [];
      // Small lists; one engagement-meta + one members fetch per row is an
      // acceptable N+1 for this scope (same tradeoff the plan calls out).
      return Promise.all(
        projects.map(async (project): Promise<EngagementRow> => {
          const [meta, members] = await Promise.all([
            fetchEngagementMeta(api, project.id).catch(() => null),
            fetchMembers(api, project.id).catch(() => []),
          ]);
          const stage = coerceStage(meta?.stage);
          return {
            id: project.id,
            name: project.name,
            code: meta?.code || project.id.toUpperCase(),
            type: meta?.type || "Advisory engagement",
            stage,
            progress: meta?.progress ?? 0,
            owner: ownerFromMembers(members),
            nextTask: meta?.next_task || "—",
            dueDate: meta?.due_date || "—",
          };
        })
      );
    },
  });
}

export function useEngagementStatsQuery(enabled = true) {
  const { api, token } = useAuth();
  return useQuery({
    queryKey: ["engagement-stats"],
    enabled: enabled && Boolean(token),
    staleTime: 60 * 1000,
    queryFn: async (): Promise<EngagementStat[]> => {
      const res = await api("/api/engagements/stats");
      const data = (await res.json().catch(() => ({}))) as {
        activeEngagements?: number;
        pendingApprovals?: number;
        openRuns?: number;
        totalProjects?: number;
      };
      if (!res.ok) throw new Error(extractApiErrorMessage(data, "Failed to load engagement stats"));
      const total = data.totalProjects ?? 0;
      const pending = data.pendingApprovals ?? 0;
      // Relabeled from the mock's 4 cards to match what the backend actually
      // aggregates (src/app/api/projects/engagement_meta.py:get_engagement_stats)
      // — no "ready to export" or "milestones" metric exists server-side.
      return [
        {
          id: "active",
          label: "Active engagements",
          value: data.activeEngagements ?? 0,
          helper: `Across ${total} engagement${total === 1 ? "" : "s"}`,
        },
        {
          id: "in-review",
          label: "Pending approvals",
          value: pending,
          helper: pending > 0 ? "Needs your response" : "Nothing waiting on you",
          helperTone: pending > 0 ? "warning" : "default",
        },
        {
          id: "open-runs",
          label: "Open runs",
          value: data.openRuns ?? 0,
          helper: "Currently generating or in progress",
        },
        {
          id: "total",
          label: "Total engagements",
          value: total,
          helper: "All engagements you can access",
        },
      ];
    },
  });
}

// No real backend equivalent (no activity log / task-assignment model) —
// kept as an empty list rather than fabricated content, so the UI shows an
// honest "nothing yet" state next to real engagement data.
export function useNextActionsQuery(enabled = true) {
  return useQuery({
    queryKey: ["engagement-next-actions"],
    enabled,
    staleTime: 5 * 60 * 1000,
    queryFn: async (): Promise<NextAction[]> => [],
  });
}

export function useRecentActivityQuery(enabled = true) {
  return useQuery({
    queryKey: ["engagement-recent-activity"],
    enabled,
    staleTime: 5 * 60 * 1000,
    queryFn: async (): Promise<ActivityItem[]> => [],
  });
}

export function useEngagementDetailQuery(id: string, enabled = true) {
  const { api, token } = useAuth();
  return useQuery({
    queryKey: ["engagement", id],
    enabled: enabled && Boolean(token) && Boolean(id),
    staleTime: 30 * 1000,
    queryFn: async (): Promise<EngagementDetail> => {
      const [projectRes, meta, members, documents] = await Promise.all([
        api(`/api/projects/${encodeURIComponent(id)}`),
        fetchEngagementMeta(api, id),
        fetchMembers(api, id),
        api(`/api/documents/list?project_id=${encodeURIComponent(id)}`)
          .then((r) => r.json().catch(() => ({})))
          .then((d: { items?: string[] }) => (Array.isArray(d.items) ? d.items : []))
          .catch(() => [] as string[]),
      ]);
      const projectData = (await projectRes.json().catch(() => ({}))) as {
        id?: string;
        name?: string;
        created_at?: string;
      };
      if (!projectRes.ok) throw new Error(extractApiErrorMessage(projectData, `Engagement "${id}" not found`));

      const stage = coerceStage(meta.stage);
      const evidenceSources: EvidenceSource[] = documents.map((path, i) => ({
        id: `doc-${i}`,
        label: path.split(/[\\/]/).pop() || path,
        value: "Indexed",
      }));

      return {
        id,
        code: meta.code || id.toUpperCase(),
        name: projectData.name || id,
        subtitle: meta.type || "Advisory engagement",
        dateRange: projectData.created_at ? `Created ${new Date(projectData.created_at).toLocaleDateString()}` : "—",
        lead: ownerFromMembers(members),
        teamMemberCount: members.length,
        steps: stepsForStage(stage),
        tabCounts: { sources: evidenceSources.length, deliverables: 0, team: members.length },
        brief: {
          updated: "",
          summary: meta.next_task || "No brief captured yet for this engagement.",
          context: "",
          sponsorObjective: "—",
          scope: "—",
          successMeasures: "—",
          classification: "Internal · Engagement-scoped",
        },
        milestones: [],
        teamMembers: members,
        teamNote: members.length ? `${members.length} team member${members.length === 1 ? "" : "s"}` : "",
        evidenceSourceCount: evidenceSources.length,
        evidenceSources,
        evidenceWarning: null,
        deliverables: [],
      };
    },
  });
}
