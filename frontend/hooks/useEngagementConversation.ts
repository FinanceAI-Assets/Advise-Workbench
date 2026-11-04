"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { extractApiErrorMessage } from "@/lib/api-error";
import { useAuth } from "@/lib/auth-context";
import { sendConversationMessage } from "@/lib/conversationTurn";
import type { ConversationMessage } from "@/types/api";

// Real-backend conversation hooks for one engagement (= project). Replaces
// the flat, single-mock useConversation.ts with a project-scoped pair:
// useConversationQuery(pid) reads history, useSendMessageMutation(pid) sends
// a turn through the same background-polling utility useRunStudio.tsx uses
// (frontend/lib/conversationTurn.ts), then invalidates the query so the
// thread refreshes with the real persisted messages.

// Raw shape of one row from GET /api/projects/{pid}/conversation's
// `messages` array — see _serialize_messages in
// src/app/api/projects/conversation.py.
export type RawConversationMessage = {
  id: number;
  role: "user" | "assistant";
  content: string;
  metadata: Record<string, unknown>;
  created_at: string | null;
};

function formatTimestamp(iso: string | null): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

/**
 * Map one real conversation row into the ConversationMessage shape
 * ConversationThread already renders. Assistant replies render as a single
 * `body` paragraph (no synthetic phases, since the backend doesn't persist
 * a phase/citation-index structure) with a trailing citation line built
 * from metadata.wiki_context_refs (plan messages) or metadata.wiki_refs
 * (conversational replies): title-only references, see conversation.py.
 * Answers from the rag_agent (metadata.kind === "rag_answer") already end
 * with their numbered source list; metadata.citations holds the details.
 */
export function toConversationMessage(raw: RawConversationMessage): ConversationMessage {
  const listed = raw.metadata?.wiki_context_refs ?? raw.metadata?.wiki_refs;
  const refs =
    raw.metadata?.kind !== "rag_answer" && Array.isArray(listed)
      ? (listed as unknown[]).filter((x): x is string => typeof x === "string")
      : [];
  const body = refs.length ? `${raw.content}\n\nSources: ${refs.join(" · ")}` : raw.content;
  return {
    id: String(raw.id),
    role: raw.role,
    author: raw.role === "user" ? "You" : "Sheldon",
    timestamp: formatTimestamp(raw.created_at),
    body,
    metadata: raw.metadata ?? {},
  };
}

export function useConversationQuery(pid: string, enabled = true) {
  const { api, token } = useAuth();
  return useQuery({
    queryKey: ["conversation", pid],
    enabled: enabled && Boolean(token) && Boolean(pid),
    staleTime: 10 * 1000,
    queryFn: async (): Promise<{ conversationId: string; messages: ConversationMessage[] }> => {
      const res = await api(`/api/projects/${encodeURIComponent(pid)}/conversation`);
      const data = (await res.json().catch(() => ({}))) as {
        conversation_id?: string;
        messages?: RawConversationMessage[];
      };
      if (!res.ok) throw new Error(extractApiErrorMessage(data, "Failed to load conversation"));
      return {
        conversationId: data.conversation_id ?? "",
        messages: (data.messages ?? []).map(toConversationMessage),
      };
    },
  });
}

// How often to check whether Sheldon has replied.
const REPLY_POLL_MS = 700;

export function useSendMessageMutation(pid: string) {
  const { api } = useAuth();
  const qc = useQueryClient();

  return useMutation({
    mutationFn: async (content: string) => {
      const sent = await sendConversationMessage(api, pid, content, undefined, REPLY_POLL_MS);
      if (!sent.ok) throw new Error(extractApiErrorMessage(sent.data, "Conversation send failed"));
      // Wait for the refreshed thread before finishing, so the sent message never blinks out.
      await qc.invalidateQueries({ queryKey: ["conversation", pid] });
      void qc.invalidateQueries({ queryKey: ["runs", pid] });
      void qc.invalidateQueries({ queryKey: ["run-progress", pid] });
      void qc.invalidateQueries({ queryKey: ["conversation-usage", pid] });
      return sent.data;
    },
  });
}
