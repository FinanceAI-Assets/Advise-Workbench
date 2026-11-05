"use client";

import { usePathname, useRouter } from "next/navigation";
import { useEffect, useMemo, useRef, useState, type MouseEvent as ReactMouseEvent } from "react";
import { useClearRunsMutation, useDeleteRunMutation, useRunsQuery } from "@/hooks/useRuns";
import { useRunStudio, type ChatMessage } from "@/hooks/useRunStudio";
import { useCoworkState } from "@/hooks/useCoworkState";
import { useRunStream } from "@/hooks/useRunStream";
import { useQueryClient } from "@tanstack/react-query";
import { useAuth } from "@/lib/auth-context";
import { extractApiErrorMessage } from "@/lib/api-error";
import { postConversationInBackground, sendConversationMessage } from "@/lib/conversationTurn";
import { formatCostCompact } from "@/lib/formatTokens";
import { useLiveTokens, useProjectTokenUsage, computeProjectTotals } from "@/hooks/useLiveTokens";

type Options = {
  pid: string;
  initialRunId?: string | null;
};

/**
 * State and actions for a project's studio: the Sheldon conversation, the selected run and its live
 * events, documents, runs and token usage. Shared by the classic project page and the step-by-step journey.
 */
export function useProjectStudio({ pid, initialRunId = null }: Options) {
  const router = useRouter();
  const pathname = usePathname();
  const { token, ready, logout, api } = useAuth();
  const [hydrated, setHydrated] = useState(false);
  const didRedirectRef = useRef(false);

  const [activeRunId, setActiveRunId] = useState<string | null>(initialRunId);
  const [sidebarWidth, setSidebarWidth] = useState(380);
  const handleSidebarResizeStart = (e: ReactMouseEvent) => {
    e.preventDefault();
    const startX = e.clientX;
    const startWidth = sidebarWidth;
    const onMouseMove = (moveEvent: MouseEvent) => {
      const delta = startX - moveEvent.clientX;
      const next = Math.min(720, Math.max(320, startWidth + delta));
      setSidebarWidth(next);
    };
    const onMouseUp = () => {
      window.removeEventListener("mousemove", onMouseMove);
      window.removeEventListener("mouseup", onMouseUp);
    };
    window.addEventListener("mousemove", onMouseMove);
    window.addEventListener("mouseup", onMouseUp);
  };
  const [chatInput, setChatInput] = useState("");
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
  const [chatBusy, setChatBusy] = useState(false);
  const [chatPhase, setChatPhase] = useState<string | null>(null);
  const [decisionBusy, setDecisionBusy] = useState(false);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [openQuestions, setOpenQuestions] = useState<string[]>([]);
  const [planHash, setPlanHash] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const qc = useQueryClient();
  const runsQuery = useRunsQuery(pid, Boolean(token && pid));
  const clearRunsMutation = useClearRunsMutation(pid);
  const deleteRunMutation = useDeleteRunMutation(pid);

  const runId = activeRunId ?? "";
  const { events, parsedEvents, status: runStatus, error: streamError, pollMode } = useRunStream(pid, runId);
  const studio = useRunStudio({
    pid,
    rid: runId,
    liveEvents: events,
    streamError,
    pollMode,
  });
  const cowork = useCoworkState({
    parsedEvents,
    messages: studio.instructionChatMessages,
    openQuestions: studio.openQuestions,
  });

  // Live token polling — polls /usage every 2 s while run is executing, stops on terminal states
  const { data: liveUsage, isLive } = useLiveTokens(pid, activeRunId, runStatus);
  // Project-wide token counter — polls even during chat (no active run needed)
  const projectLiveUsage = useProjectTokenUsage(pid, isLive || chatBusy || studio.chatBusy);

  // When run reaches a terminal state, refetch the runs list so final token/cost values appear
  const prevRunStatusRef = useRef<string>("");
  useEffect(() => {
    const TERMINAL = new Set(["review_ready", "done", "failed"]);
    if (TERMINAL.has(runStatus) && !TERMINAL.has(prevRunStatusRef.current)) {
      void qc.invalidateQueries({ queryKey: ["runs", pid] });
      void qc.invalidateQueries({ queryKey: ["run-live-usage", pid, activeRunId] });
    }
    prevRunStatusRef.current = runStatus;
  }, [runStatus, pid, activeRunId, qc]);

  const latestAssistantMetadata = useMemo(() => {
    for (let i = chatMessages.length - 1; i >= 0; i -= 1) {
      const m = chatMessages[i];
      if (m.role === "assistant" && m.metadata) return m.metadata;
    }
    return null;
  }, [chatMessages]);

  const decisionPrompts = useMemo(
    () => (Array.isArray(latestAssistantMetadata?.decision_prompts) ? latestAssistantMetadata.decision_prompts : []),
    [latestAssistantMetadata]
  );
  const unresolvedPromptIds = useMemo(
    () =>
      Array.isArray(latestAssistantMetadata?.unresolved_prompt_ids)
        ? latestAssistantMetadata.unresolved_prompt_ids.filter((x): x is string => typeof x === "string")
        : [],
    [latestAssistantMetadata]
  );

  useEffect(() => {
    setHydrated(true);
  }, []);

  useEffect(() => {
    if (!ready) return;
    if (!token) {
      if (didRedirectRef.current) return;
      didRedirectRef.current = true;
      router.replace(`/login?next=${encodeURIComponent(pathname || `/projects/${pid}`)}`);
    }
  }, [ready, token, pid, pathname, router]);

  useEffect(() => {
    if (!activeRunId) return;
    const query = new URLSearchParams(window.location.search);
    query.set("run", activeRunId);
    router.replace(`/projects/${pid}?${query.toString()}`);
  }, [activeRunId, pid, router]);

  const activeOpenQuestions = useMemo(
    () => activeRunId ? studio.openQuestions : openQuestions,
    [activeRunId, studio.openQuestions, openQuestions]
  );

  // Use latest messages: if user has sent messages (chatMessages updated), use those
  // Otherwise use studio messages which includes greeting on mount
  const activeMessages = useMemo(
    () => chatMessages.length > 0 ? chatMessages : studio.instructionChatMessages,
    [chatMessages, studio.instructionChatMessages]
  );

  const agreedDecisions = useMemo(() => {
    const msgs = activeMessages;
    for (let i = msgs.length - 1; i >= 0; i--) {
      const m = msgs[i];
      if (m.role === "assistant" && m.metadata?.kind === "structure_summary" && Array.isArray(m.metadata.slides)) {
        return m.metadata.slides as Array<{ slide_num: number; title: string; key_message?: string; slide_type?: string; agreed?: boolean }>;
      }
    }
    return msgs
      .filter((m) => m.role === "assistant" && m.metadata?.kind === "slide_proposal" && m.metadata.slide?.agreed)
      .map((m) => m.metadata!.slide as { slide_num: number; title: string; key_message?: string; slide_type?: string; agreed?: boolean });
  }, [activeMessages]);

  const activeChatBusy = useMemo(
    () => activeRunId ? studio.chatBusy : chatBusy,
    [activeRunId, studio.chatBusy, chatBusy]
  );

  // Prefer studio conversation ID if available (from initial greeting load)
  const activeConversationId = useMemo(
    () => studio.conversationId || conversationId,
    [studio.conversationId, conversationId]
  );

  const activeDecisionPrompts = useMemo(
    () => activeRunId ? studio.decisionPrompts : decisionPrompts,
    [activeRunId, studio.decisionPrompts, decisionPrompts]
  );

  const activeUnresolvedPromptIds = useMemo(
    () => activeRunId ? studio.unresolvedPromptIds : unresolvedPromptIds,
    [activeRunId, studio.unresolvedPromptIds, unresolvedPromptIds]
  );

  const activeRun = useMemo(
    () => (runsQuery.data ?? []).find((r) => r.id === activeRunId) ?? null,
    [runsQuery.data, activeRunId]
  );

  const projectTotals = useMemo(
    () => computeProjectTotals(runsQuery.data ?? []),
    [runsQuery.data]
  );

  // Token/cost data to display: prefer live polling data for the current run, else DB values
  const displayUsage = useMemo(() => {
    if (liveUsage) return liveUsage;
    if (!activeRun) return null;
    return {
      input_tokens: activeRun.tokens_input ?? 0,
      output_tokens: activeRun.tokens_output ?? 0,
      cache_read_tokens: activeRun.tokens_cache_read ?? 0,
      cache_creation_tokens: activeRun.tokens_cache_creation ?? 0,
      cost_usd: activeRun.cost_usd ?? null,
      live: false,
    };
  }, [liveUsage, activeRun]);

  // Session-wide cost/tokens: live project total (process-local, resets on backend restart)
  // floored by the DB-backed total across all runs, so a restart never makes the number drop.
  const liveSessionTokens = projectLiveUsage
    ? (projectLiveUsage.input_tokens + projectLiveUsage.output_tokens +
       projectLiveUsage.cache_read_tokens + projectLiveUsage.cache_creation_tokens)
    : 0;
  const sessionCostUsd = Math.max(projectLiveUsage?.cost_usd ?? 0, projectTotals.totalCost);
  const sessionCostLabel = formatCostCompact(sessionCostUsd);
  const sessionTokens = Math.max(liveSessionTokens, projectTotals.totalTokens);

  async function sendMessage() {
    await sendText(chatInput);
  }

  /** Send a message to Sheldon without going through the chat input (used by the journey's step actions). */
  async function sendText(text: string) {
    const msg = text.trim();
    if (chatBusy || !msg) return;
    setChatBusy(true);
    setError(null);
    try {
      setChatInput("");
      const sent = await sendConversationMessage(api, pid, msg, setChatPhase);
      const data = sent.data as {
        conversation_id?: string;
        open_questions?: string[];
        ready_for_confirmation?: boolean;
        plan_hash?: string;
        run_id?: string;
        auto_executed?: boolean;
        messages?: Array<{
          id: number;
          role: "user" | "assistant";
          content: string;
          metadata?: ChatMessage["metadata"];
          created_at?: string | null;
        }>;
      };
      if (!sent.ok) throw new Error(extractApiErrorMessage(data, "Conversation send failed"));
      setConversationId(data.conversation_id ?? conversationId);
      setOpenQuestions(Array.isArray(data.open_questions) ? data.open_questions : []);
      setPlanHash(typeof data.plan_hash === "string" && data.plan_hash ? data.plan_hash : null);
      const mapped = Array.isArray(data.messages)
        ? data.messages.map((m) => ({
            id: m.id,
            role: m.role,
            content: m.content,
            metadata: m.metadata,
            ts: m.created_at ? Date.parse(m.created_at) : Date.now(),
          }))
        : [];
      setChatMessages(mapped);
      if (data.auto_executed && typeof data.run_id === "string" && data.run_id) {
        setActiveRunId(data.run_id);
        void qc.invalidateQueries({ queryKey: ["active-runs", pid] });
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Conversation send failed");
    } finally {
      setChatBusy(false);
      setChatPhase(null);
    }
  }

  async function submitDecisionAnswers(
    answers: Record<string, string[] | { selected_values?: string[]; free_text?: string }>
  ) {
    if (!conversationId || decisionBusy) return;
    setDecisionBusy(true);
    setError(null);
    try {
      const payload = Object.entries(answers).map(([prompt_id, entry]) => {
        if (Array.isArray(entry)) {
          return { prompt_id, selected_values: entry };
        }
        return {
          prompt_id,
          selected_values: entry?.selected_values ?? [],
          free_text: entry?.free_text && entry.free_text.trim() ? entry.free_text.trim() : undefined,
        };
      });
      const sent = await postConversationInBackground(api, pid, "decisions", {
          conversation_id: conversationId,
          plan_hash: planHash ?? undefined,
          answers: payload,
        });
      const data = sent.data as {
        conversation_id?: string;
        open_questions?: string[];
        ready_for_confirmation?: boolean;
        plan_hash?: string;
        messages?: Array<{ id: number; role: "user" | "assistant"; content: string; metadata?: ChatMessage["metadata"]; created_at?: string | null }>;
      };
      if (!sent.ok) throw new Error(extractApiErrorMessage(data, "Failed to apply decision updates"));
      setConversationId(data.conversation_id ?? conversationId);
      setOpenQuestions(Array.isArray(data.open_questions) ? data.open_questions : []);
      setPlanHash(typeof data.plan_hash === "string" && data.plan_hash ? data.plan_hash : null);
      const mapped = Array.isArray(data.messages)
        ? data.messages.map((m) => ({
            id: m.id,
            role: m.role,
            content: m.content,
            metadata: m.metadata,
            ts: m.created_at ? Date.parse(m.created_at) : Date.now(),
          }))
        : [];
      setChatMessages(mapped);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to apply decision updates");
    } finally {
      setDecisionBusy(false);
    }
  }

  /** Save an edited slide outline for the current plan (before a run exists). */
  async function updateOutline(slides: Array<{ title: string; slide_type: string; purpose?: string }>) {
    if (!conversationId || !planHash || decisionBusy) return;
    setDecisionBusy(true);
    setError(null);
    try {
      const sent = await postConversationInBackground(api, pid, "outline", {
        conversation_id: conversationId,
        plan_hash: planHash,
        slides,
      });
      const data = sent.data as {
        plan_hash?: string;
        messages?: Array<{ id: number; role: "user" | "assistant"; content: string; metadata?: ChatMessage["metadata"]; created_at?: string | null }>;
      };
      if (!sent.ok) throw new Error(extractApiErrorMessage(data, "Failed to save the outline"));
      if (typeof data.plan_hash === "string" && data.plan_hash) setPlanHash(data.plan_hash);
      if (Array.isArray(data.messages)) {
        setChatMessages(
          data.messages.map((m) => ({
            id: m.id,
            role: m.role,
            content: m.content,
            metadata: m.metadata,
            ts: m.created_at ? Date.parse(m.created_at) : Date.now(),
          })),
        );
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to save the outline");
    } finally {
      setDecisionBusy(false);
    }
  }

  async function clearRuns() {
    if (clearRunsMutation.isPending) return;
    const ok = window.confirm("Clear all recent runs for this project?");
    if (!ok) return;
    setError(null);
    try {
      await clearRunsMutation.mutateAsync();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to clear runs");
    }
  }

  async function deleteRun(runIdValue: string) {
    if (deleteRunMutation.isPending) return;
    const ok = window.confirm(`Delete run ${runIdValue}?`);
    if (!ok) return;
    try {
      await deleteRunMutation.mutateAsync(runIdValue);
      if (activeRunId === runIdValue) {
        setActiveRunId(null);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to delete run");
    }
  }


  return {
    hydrated,
    activeRunId,
    setActiveRunId,
    sidebarWidth,
    chatInput,
    setChatInput,
    chatMessages,
    chatBusy,
    chatPhase,
    decisionBusy,
    conversationId,
    openQuestions,
    error,
    token,
    ready,
    logout,
    events,
    parsedEvents,
    streamError,
    pollMode,
    isLive,
    handleSidebarResizeStart,
    runsQuery,
    clearRunsMutation,
    runId,
    studio,
    cowork,
    decisionPrompts,
    unresolvedPromptIds,
    activeOpenQuestions,
    activeMessages,
    agreedDecisions,
    activeChatBusy,
    activeConversationId,
    activeDecisionPrompts,
    activeUnresolvedPromptIds,
    displayUsage,
    sessionCostLabel,
    sessionTokens,
    sendMessage,
    sendText,
    updateOutline,
    api,
    runStatus,
    planHash,
    activeRun,
    submitDecisionAnswers,
    clearRuns,
    deleteRun,
  };
}

export type ProjectStudio = ReturnType<typeof useProjectStudio>;
