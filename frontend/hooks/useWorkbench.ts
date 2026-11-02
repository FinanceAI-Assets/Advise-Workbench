"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { useAuth } from "@/lib/auth-context";
import { fetchJson } from "@/lib/workbenchApi";
import type { AuthUser, LPLibraryDetail, PracticeDetail, ReviewDetail, SkillsDetail } from "@/types/api";

// Hooks for the workbench screens outside the engagement pages: conversations,
// reviews, library, skills, notifications, search and the profile.

function useWorkbenchQuery<T>(key: unknown[], path: string, fallback: string, enabled = true) {
  const { api, token } = useAuth();
  return useQuery({
    queryKey: key,
    enabled: enabled && Boolean(token),
    staleTime: 15 * 1000,
    queryFn: () => fetchJson<T>(api, path, fallback),
  });
}

/** POST/PUT/DELETE helper: `invalidate` lists the query keys to refresh afterwards. */
function useWorkbenchMutation<TBody = void, TResult = unknown>(
  build: (body: TBody) => { path: string; method?: string; body?: unknown },
  fallback: string,
  invalidate: unknown[][]
) {
  const { api } = useAuth();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: TBody) => {
      const request = build(input);
      return fetchJson<TResult>(api, request.path, fallback, {
        method: request.method ?? "POST",
        body: request.body === undefined ? undefined : JSON.stringify(request.body),
      });
    },
    onSuccess: () => {
      for (const key of invalidate) void qc.invalidateQueries({ queryKey: key });
    },
  });
}

// --- Conversations -------------------------------------------------------

export type ConversationContext = {
  items: Array<{ id: string; label: string; active: boolean; updated: string }>;
  skill: { id: string; name: string; version: string; meta: string; formats: string[] } | null;
  skills: Array<{ id: string; name: string; version: string; formats: string }>;
  sources: { documents: string[]; practices: Array<{ id: string; title: string }>; total: number };
};

const enc = encodeURIComponent;

export function useConversationContextQuery(pid: string) {
  return useWorkbenchQuery<ConversationContext>(
    ["conversation-context", pid],
    `/api/engagements/${enc(pid)}/conversations`,
    "Failed to load conversations",
    Boolean(pid)
  );
}

export type ConversationUsage = {
  conversationId: string | null;
  model: string;
  inputTokens: number;
  outputTokens: number;
  cacheReadTokens: number;
  cacheCreationTokens: number;
  totalTokens: number;
  costUsd: number;
  replies: number;
  live: boolean;
  pricing: { inputPerMillion: number; outputPerMillion: number };
};

/** Usage for the active conversation; refreshed every two seconds while a reply is being written. */
export function useConversationUsageQuery(pid: string, busy: boolean) {
  const { api, token } = useAuth();
  return useQuery({
    queryKey: ["conversation-usage", pid],
    enabled: Boolean(token) && Boolean(pid),
    refetchInterval: busy ? 2000 : false,
    queryFn: () =>
      fetchJson<ConversationUsage>(api, `/api/engagements/${enc(pid)}/conversations/usage`, "Failed to load usage"),
  });
}

export function useStartConversationMutation(pid: string) {
  return useWorkbenchMutation<string>(
    (title) => ({ path: `/api/engagements/${enc(pid)}/conversations`, body: { title } }),
    "Could not start the conversation",
    [["conversation-context", pid], ["conversation", pid], ["conversation-usage", pid]]
  );
}

/** Start a conversation in an engagement chosen at call time (the Conversation picker page). */
export function useStartConversationInMutation() {
  return useWorkbenchMutation<{ pid: string; title: string }>(
    ({ pid, title }) => ({ path: `/api/engagements/${enc(pid)}/conversations`, body: { title } }),
    "Could not start the conversation",
    [["conversation-context"], ["conversation"], ["conversation-usage"]]
  );
}

export function useActivateConversationMutation(pid: string) {
  return useWorkbenchMutation<string>(
    (cid) => ({ path: `/api/engagements/${enc(pid)}/conversations/${enc(cid)}/activate` }),
    "Could not open the conversation",
    [["conversation-context", pid], ["conversation", pid], ["conversation-usage", pid]]
  );
}

export function useSelectSkillMutation() {
  return useWorkbenchMutation<{ skillId: string; projectId: string }, { href: string }>(
    ({ skillId, projectId }) => ({ path: `/api/skills/${enc(skillId)}/select`, body: { projectId } }),
    "Could not select the skill",
    [["conversation-context"]]
  );
}

export type RunProgress = {
  id: string;
  status: string;
  instruction: string;
  active: boolean;
  finished: boolean;
  failed: boolean;
  needsApproval: boolean;
  error: string;
  elapsedSeconds: number;
  lastUpdateSeconds: number;
  outputs: string[];
  stages: Array<{ id: string; label: string; state: "done" | "current" | "upcoming" }>;
};

/** Progress of the latest draft generation; checked every four seconds while it is working. */
export function useRunProgressQuery(pid: string) {
  const { api, token } = useAuth();
  return useQuery({
    queryKey: ["run-progress", pid],
    enabled: Boolean(token) && Boolean(pid),
    refetchInterval: (query) => {
      const run = query.state.data?.run;
      return run && (run.active || run.needsApproval) ? 4000 : false;
    },
    queryFn: () =>
      fetchJson<{ run: RunProgress | null }>(api, `/api/engagements/${enc(pid)}/run-progress`, "Failed to load progress"),
  });
}

export function useApproveRunMutation(pid: string) {
  return useWorkbenchMutation<string>(
    (runId) => ({ path: `/api/runs/${enc(pid)}/${enc(runId)}/approve` }),
    "Could not approve the plan",
    [["runs", pid], ["deliverables", pid], ["run-progress", pid]]
  );
}

// --- Reviews -------------------------------------------------------------

export type ReviewRow = {
  id: string;
  title: string;
  engagement: string;
  projectId: string | null;
  type: string;
  owner: string;
  reviewer: string;
  dueDate: string;
  state: string;
  risk: string;
};

export type ReviewView = ReviewDetail & {
  projectId: string | null;
  runId: string | null;
  artifactType: string;
  state: string;
  canRevise: boolean;
  canDecide: boolean;
  canComment: boolean;
};

export function useReviewsQuery() {
  return useWorkbenchQuery<{ items: ReviewRow[]; mine: string[]; total: number }>(
    ["reviews"],
    "/api/reviews",
    "Failed to load reviews"
  );
}

export function useReviewQuery(id: string) {
  return useWorkbenchQuery<ReviewView>(["review", id], `/api/reviews/${enc(id)}`, "Review not found", Boolean(id));
}

const REVIEW_KEYS = (id: string) => [["review", id], ["reviews"], ["engagement-stats"], ["engagement-next-actions"]];

export function useReviewActions(id: string) {
  const base = `/api/reviews/${enc(id)}`;
  return {
    resolve: useWorkbenchMutation<string>(
      (commentId) => ({ path: `${base}/comments/${enc(commentId)}/resolve` }),
      "Could not update the comment",
      REVIEW_KEYS(id)
    ),
    comment: useWorkbenchMutation<{ title: string; body: string }>(
      (body) => ({ path: `${base}/comments`, body }),
      "Could not add the comment",
      REVIEW_KEYS(id)
    ),
    submitRevision: useWorkbenchMutation<string>(
      (note) => ({ path: `${base}/submit-revision`, body: { note } }),
      "Could not submit the revision",
      REVIEW_KEYS(id)
    ),
    decide: useWorkbenchMutation<{ decision: "approve" | "request_changes"; note: string }>(
      (body) => ({ path: `${base}/decision`, body }),
      "Could not record the decision",
      REVIEW_KEYS(id)
    ),
  };
}

export type SubmitReviewInput = {
  projectId: string;
  runId: string;
  artifactType: "pptx" | "docx";
  title: string;
  reviewerId: string;
  dueDate: string;
};

export function useSubmitForReviewMutation() {
  return useWorkbenchMutation<SubmitReviewInput, { id: string }>(
    (body) => ({ path: "/api/reviews", body }),
    "Could not submit for review",
    [["reviews"], ["engagement"], ["engagement-stats"]]
  );
}

// --- Library and skills --------------------------------------------------

export type LibraryFilters = { q: string; category: string; maturity: string; sort: string; savedOnly: boolean };

export type LibraryView = Omit<LPLibraryDetail, "practices" | "cards"> & {
  cards: Array<LPLibraryDetail["cards"][number] & { saved: boolean }>;
  maturities: string[];
  savedCount: number;
};

export function useLibraryQuery(filters: LibraryFilters) {
  const params = new URLSearchParams({
    q: filters.q,
    category: filters.category,
    maturity: filters.maturity,
    sort: filters.sort,
    saved_only: String(filters.savedOnly),
  });
  return useWorkbenchQuery<LibraryView>(["library", filters], `/api/library?${params}`, "Failed to load the library");
}

export function usePracticeQuery(id: string) {
  return useWorkbenchQuery<PracticeDetail & { saved: boolean }>(
    ["practice", id],
    `/api/library/${enc(id)}`,
    "Practice not found",
    Boolean(id)
  );
}

export function usePracticeActions(id: string) {
  const base = `/api/library/${enc(id)}`;
  const keys = [["library"], ["practice", id], ["engagement"]];
  return {
    save: useWorkbenchMutation<boolean>(
      (saved) => ({ path: `${base}/save`, method: saved ? "POST" : "DELETE" }),
      "Could not update saved practices",
      keys
    ),
    addToEngagement: useWorkbenchMutation<string, { added: boolean }>(
      (projectId) => ({ path: `${base}/add-to-engagement`, body: { projectId } }),
      "Could not add the practice",
      keys
    ),
  };
}

export type LibraryAnswer = {
  answer: string;
  practices: Array<{ id: string; title: string; category: string }>;
  documents: Array<{ practiceId: string; practice: string; filename: string }>;
  // practiceId is empty for passages from library files outside the approved catalog.
  sources: Array<{ heading: string; source: string; text: string; practiceId: string }>;
};

/** Talk to data: `practiceIds` limits the answer to those approved practices ("Ask selected sources only"). */
export type LibraryQuestion = { question: string; practiceIds?: string[]; maxResults?: number };

export function useLibraryAskMutation() {
  return useWorkbenchMutation<LibraryQuestion, LibraryAnswer>(
    (body) => ({ path: "/api/library/ask", body }),
    "Could not answer the question",
    []
  );
}

/** The signed-in user's active engagements, for the "Use in engagement" destination picker. */
export function useMyEngagementOptionsQuery() {
  return useWorkbenchQuery<{ items: Array<{ id: string; name: string; code: string }> }>(
    ["engagements", "options"],
    "/api/engagements?status=active&mine=true&page=1&page_size=100",
    "Failed to load engagements"
  );
}

export type LibraryHandoff = {
  projectId: string;
  practiceIds: string[];
  // An existing conversation to continue, or the title of a new one.
  conversation: { id: string } | { title: string };
  brief: string;
};

/** Key under which the handoff brief waits for the engagement conversation page to put it in the composer. */
export const handoffDraftKey = (pid: string) => `aw:library-handoff:${pid}`;

/**
 * Use in engagement: add each selected practice to the engagement's sources, open the target conversation,
 * and leave the edited brief as a draft there. Nothing is sent to Sheldon and no artifact is generated.
 */
export function useLibraryHandoffMutation() {
  const { api } = useAuth();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ projectId, practiceIds, conversation, brief }: LibraryHandoff) => {
      for (const id of practiceIds) {
        await fetchJson(api, `/api/library/${enc(id)}/add-to-engagement`, `Could not add ${id.toUpperCase()}`, {
          method: "POST",
          body: JSON.stringify({ projectId }),
        });
      }
      const base = `/api/engagements/${enc(projectId)}/conversations`;
      if ("title" in conversation) {
        await fetchJson(api, base, "Could not start the conversation", {
          method: "POST",
          body: JSON.stringify({ title: conversation.title }),
        });
      } else {
        await fetchJson(api, `${base}/${enc(conversation.id)}/activate`, "Could not open the conversation", { method: "POST" });
      }
      if (brief.trim()) window.sessionStorage.setItem(handoffDraftKey(projectId), brief.trim());
      return { projectId };
    },
    onSettled: (_data, _error, { projectId }) => {
      for (const key of [["library"], ["practice"], ["engagement", projectId], ["conversation-context", projectId], ["conversation", projectId]]) {
        void qc.invalidateQueries({ queryKey: key });
      }
    },
  });
}

export function useSkillsQuery(q: string) {
  return useWorkbenchQuery<SkillsDetail>(["skills", q], `/api/skills?q=${enc(q)}`, "Failed to load skills");
}

export type SkillRun = {
  id: string;
  projectId: string;
  engagement: string;
  skill: string;
  outputs: string;
  status: string;
  when: string;
  instruction: string;
};

export function useSkillRunsQuery() {
  return useWorkbenchQuery<{ items: SkillRun[] }>(["skill-runs"], "/api/skills/runs", "Failed to load run history");
}

// --- Header: notifications, search, profile ------------------------------

export type NotificationItem = {
  id: number;
  kind: string;
  title: string;
  body: string;
  link: string;
  read: boolean;
  when: string;
};

export type NotificationFilter = "all" | "unread" | "mentions" | "system";

export function useNotificationsQuery(filter: NotificationFilter) {
  return useWorkbenchQuery<{ items: NotificationItem[]; counts: Record<NotificationFilter, number> }>(
    ["notifications", filter],
    `/api/notifications?filter=${filter}`,
    "Failed to load notifications"
  );
}

export function useNotificationActions() {
  return {
    read: useWorkbenchMutation<number>(
      (id) => ({ path: `/api/notifications/${id}/read` }),
      "Could not update the notification",
      [["notifications"]]
    ),
    readAll: useWorkbenchMutation<void>(
      () => ({ path: "/api/notifications/read-all" }),
      "Could not update notifications",
      [["notifications"]]
    ),
  };
}

export type SearchHit = { id: string; title: string; meta: string; href: string };

export function useSearchQuery(q: string) {
  return useWorkbenchQuery<{ engagements: SearchHit[]; practices: SearchHit[]; artifacts: SearchHit[] }>(
    ["search", q],
    `/api/search?q=${enc(q)}`,
    "Search failed",
    q.trim().length >= 2
  );
}

export function useUpdateProfileMutation() {
  return useWorkbenchMutation<{ full_name: string; job_title: string }, AuthUser>(
    (body) => ({ path: "/api/auth/me", method: "PATCH", body }),
    "Could not save your profile",
    []
  );
}
