"use client";

import Link from "next/link";
import { useState, type CSSProperties } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";
import { DocumentUploader } from "@/components/documents/DocumentUploader";
import { EmptyState } from "@/components/ui/EmptyState";
import { ZonePanelErrorBoundary } from "@/components/ErrorBoundary";
import { ToolActivityFeed } from "@/components/run-studio/ToolActivityFeed";
import { ApprovalBanner } from "@/components/run-studio/ApprovalBanner";
import { ZoneAInstruction } from "@/components/run-studio/ZoneAInstruction";
import { ZoneCLiveMonitor } from "@/components/run-studio/ZoneCLiveMonitor";
import { RunHealthPanel } from "@/components/run-studio/RunHealthPanel";
import { ActivityTodoList } from "@/components/activity/ActivityTodoList";
import { WikiQuickAccess } from "@/components/wiki/WikiQuickAccess";
import { Button } from "@/components/ui/Button";
import { buildTokenBreakdown, formatCostCompact, formatTokenCount } from "@/lib/formatTokens";
import { useProjectStudio } from "@/hooks/useProjectStudio";


type Props = {
  pid: string;
  initialRunId?: string | null;
};

function CollapsibleSection({
  title,
  defaultOpen = true,
  children,
}: {
  title: string;
  defaultOpen?: boolean;
  children: React.ReactNode;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <section className="border border-[var(--surface-border)] bg-white">
      <button
        type="button"
        className="flex min-h-11 w-full items-center justify-between px-3 py-2 text-left"
        onClick={() => setOpen((prev) => !prev)}
        aria-expanded={open}
      >
        <span className="text-xs font-semibold uppercase tracking-wide text-[var(--text-muted)]">{title}</span>
        {open ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
      </button>
      {open ? <div className="border-t border-[var(--surface-border)] p-3">{children}</div> : null}
    </section>
  );
}

export function ProjectStudioUnified({ pid, initialRunId = null }: Props) {
  const {
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
    updateOutline,
    submitDecisionAnswers,
    clearRuns,
    deleteRun,
  } = useProjectStudio({ pid, initialRunId });

  if (!hydrated || !ready || !token) {
    return <main style={{ padding: 24 }}><p>Redirecting…</p></main>;
  }

  return (
    <main className="project-studio-compact space-y-3">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold">Project {pid}</h1>
          <p className="text-xs text-[var(--text-muted)]">
            Unified Project + Studio workspace ·{" "}
            <Link href={`/v2/projects/${pid}`} className="underline">
              Try the guided view
            </Link>
          </p>
        </div>
        <div className="flex items-center gap-3">
          {/* Token meter — always visible, updates during chat and runs */}
          <div className="flex items-center gap-2 border border-[var(--surface-border)] bg-white px-3 py-1.5 text-xs">
            <span className="text-[var(--text-muted)]">Session</span>
            <span className="font-mono font-medium">
              {formatTokenCount(sessionTokens)} tok
            </span>
            <span className="text-[var(--text-muted)]">·</span>
            <span className="font-mono font-semibold text-[var(--accent-blue)]">
              {sessionCostLabel}
            </span>
            {(isLive || chatBusy || studio.chatBusy) && (
              <span className="inline-block animate-spin text-[var(--accent-blue)]">↻</span>
            )}
          </div>
          <Button type="button" variant="ghost" onClick={logout}>Sign out</Button>
        </div>
      </header>

      {error ?<div className="alert alert--error p-2 text-sm">{error}</div> : null}

      <section
        className="grid gap-3 lg:grid-cols-[minmax(0,1fr)_var(--sidebar-width)]"
        style={{ "--sidebar-width": `${sidebarWidth}px` } as CSSProperties}
      >
        <section className="min-w-0 space-y-3">
          {chatPhase ? (
            <p role="status" className="px-3 py-1 text-xs text-[var(--text-muted)]">Sheldon: {chatPhase}…</p>
          ) : null}
          <ZonePanelErrorBoundary label="Instruction chat">
            <ZoneAInstruction
              projectId={pid}
              recommendationNote={activeRunId ? studio.recommendationNote : null}
              chatMessages={activeMessages}
              chatInput={activeRunId ? studio.chatInput : chatInput}
              setChatInput={activeRunId ? studio.setChatInput : setChatInput}
              chatBusy={activeChatBusy}
              onSendChat={activeRunId ? studio.sendChatMessage : sendMessage}
              conversationId={activeConversationId}
              openQuestions={activeOpenQuestions}
              decisionPrompts={activeDecisionPrompts}
              unresolvedPromptIds={activeUnresolvedPromptIds}
              onSubmitDecisions={activeRunId ? studio.submitDecisionAnswers : submitDecisionAnswers}
              decisionBusy={activeRunId ? studio.decisionBusy : decisionBusy}
              onUpdateOutline={activeRunId ? studio.updateConversationOutline : updateOutline}
              thinkingStatements={cowork.thinkingStatements}
              hasThinkingTrace={cowork.hasThinkingTrace}
              thinkingTrace={cowork.thinkingTrace}
              thinkingExpanded={cowork.thinkingExpanded}
              onToggleThinkingTrace={() => cowork.setThinkingExpanded((prev) => !prev)}
            />
          </ZonePanelErrorBoundary>
          {activeRunId ? (
            <ApprovalBanner state={studio.approvalBannerState} />
          ) : null}
        </section>

        <aside className="relative min-w-0">
          {/* eslint-disable-next-line jsx-a11y/no-noninteractive-element-interactions -- drag resize handle */}
          <div
            className="absolute -left-3 top-0 z-10 hidden h-full w-3 cursor-col-resize lg:block"
            onMouseDown={handleSidebarResizeStart}
            role="separator"
            aria-orientation="vertical"
            aria-label="Resize sidebar panel"
          />
          <div className="space-y-3 border-l border-[var(--surface-border)] pl-3 bg-[var(--surface-muted)]">
          <CollapsibleSection title="Run Health" defaultOpen={true}>
            <RunHealthPanel projectId={pid} onSelectRun={(runId) => setActiveRunId(runId)} />
          </CollapsibleSection>

          <CollapsibleSection title="Project Documents" defaultOpen={true}>
            <DocumentUploader projectId={pid} />
          </CollapsibleSection>

          <CollapsibleSection title="Activity" defaultOpen={Boolean(activeRunId)}>
            <div className="space-y-4">
              {/* Project Activity To-Do List */}
              <ActivityTodoList
                projectId={pid}
                onTodoClick={(runId) => setActiveRunId(runId)}
                maxItems={10}
              />

              {/* Selected Run Activity Feed */}
              {activeRunId && (
                <div className="border-t pt-4">
                  <h4 className="text-sm font-semibold mb-3">Selected Run Activity</h4>
                  <ZonePanelErrorBoundary label="Activity feed">
                    <ToolActivityFeed
                      events={events}
                      parsedEvents={parsedEvents}
                      runChecklistTodos={studio.runChecklistTodos}
                      artifacts={studio.artifacts}
                      pollMode={pollMode}
                      streamError={streamError}
                      downloadsContent={studio.downloadsContent}
                      onTaskAction={studio.applyTaskAction}
                      onRegenerateSlide={studio.regenerateSlide}
                      onPatchSlideElement={studio.patchSlideElement}
                      slideRegenerateBusyIndex={studio.slideRegenerateBusyIndex}
                      hooksPanel={studio.hooksPanel}
                      permissionPanel={studio.permissionPanel}
                      projectId={pid}
                      runId={activeRunId ?? undefined}
                      agreedDecisions={agreedDecisions}
                    />
                  </ZonePanelErrorBoundary>
                </div>
              )}
            </div>
          </CollapsibleSection>

          <CollapsibleSection title="Execution Audit Trail" defaultOpen={Boolean(activeRunId)}>
            {activeRunId ? (
              <ZonePanelErrorBoundary label="Execution audit trail">
                <ZoneCLiveMonitor
                  events={events}
                  showAgentGraph={false}
                  runControls={studio.runControls}
                  evaluatorSummary={
                    studio.evaluatorSummary
                      ? {
                          qaPassed: Boolean(studio.evaluatorSummary.qa_passed),
                          visualQaPassed: Boolean(studio.evaluatorSummary.visual_qa_passed),
                          guardrailsPassed: Boolean(studio.evaluatorSummary.guardrails_passed),
                          status: studio.evaluatorSummary.status,
                        }
                      : null
                  }
                />
              </ZonePanelErrorBoundary>
            ) : (
              <p className="text-xs text-[var(--text-muted)]">Select a run to view execution events.</p>
            )}
          </CollapsibleSection>

          <CollapsibleSection title="Runs" defaultOpen={true}>
            <div className="max-h-[260px] space-y-1 overflow-auto">
              {(runsQuery.data ?? []).map((r) => (
                <div key={r.id} className="flex items-center justify-between gap-2 rounded border border-[var(--surface-border)] px-2 py-1.5">
                  <button
                    type="button"
                    className={`truncate text-left text-xs ${activeRunId === r.id ? "text-[var(--accent-blue)]" : ""}`}
                    onClick={() => setActiveRunId(r.id)}
                    title={`${r.id} · ${r.status}`}
                  >
                    {r.id} · {r.status}
                    {(() => {
                      const runTokens =
                        (r.tokens_input ?? 0) + (r.tokens_output ?? 0) +
                        (r.tokens_cache_read ?? 0) + (r.tokens_cache_creation ?? 0);
                      return (
                        (runTokens > 0 || formatCostCompact(r.cost_usd)) && (
                          <span className="ml-1.5 text-[var(--text-muted)]">
                            {runTokens > 0 ? `${formatTokenCount(runTokens)} tok` : null}
                            {runTokens > 0 && formatCostCompact(r.cost_usd) ? " · " : null}
                            {formatCostCompact(r.cost_usd)}
                          </span>
                        )
                      );
                    })()}
                  </button>
                  <button type="button" className="text-2xs text-[var(--error)]" onClick={() => void deleteRun(r.id)}>Delete</button>
                </div>
              ))}
              {(runsQuery.data ?? []).length === 0 ? (
                <EmptyState title="No runs yet" description="Start a new run to see execution history here." />
              ) : null}
            </div>
            {/* Token breakdown — always visible when a run is selected */}
            {activeRunId && (
              <div className="mt-2 border border-[var(--surface-border)] bg-white p-3 text-xs">
                <div className="flex items-center justify-between mb-1">
                  <span className="font-medium text-[var(--text-primary)]">
                    Token Usage
                    {isLive && (
                      <span className="ml-1.5 inline-block animate-spin text-[var(--accent-blue)]">↻</span>
                    )}
                  </span>
                  <span className="font-mono font-semibold text-[var(--accent-blue)]">
                    {formatCostCompact(displayUsage?.cost_usd ?? null)}
                  </span>
                </div>
                {displayUsage ? (
                  <table className="w-full">
                    <thead>
                      <tr className="text-[var(--text-muted)]">
                        <th className="text-left font-normal pb-1">Category</th>
                        <th className="text-right font-normal pb-1">Tokens</th>
                        <th className="text-right font-normal pb-1">Rate</th>
                        <th className="text-right font-normal pb-1">Cost</th>
                      </tr>
                    </thead>
                    <tbody>
                      {(buildTokenBreakdown(displayUsage) ?? [
                        { label: "Input", tokens: 0, rate: "$3.00/MTok", cost: "$0.0000" },
                        { label: "Output", tokens: 0, rate: "$15.00/MTok", cost: "$0.0000" },
                      ]).map((row) => (
                        <tr key={row.label} className="border-t border-[var(--surface-border)]">
                          <td className="py-0.5">{row.label}</td>
                          <td className="py-0.5 text-right font-mono">{row.tokens.toLocaleString()}</td>
                          <td className="py-0.5 text-right text-[var(--text-muted)]">{row.rate}</td>
                          <td className="py-0.5 text-right font-mono">{row.cost}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                ) : (
                  <p className="text-[var(--text-muted)]">Waiting for first LLM call…</p>
                )}
              </div>
            )}
            <div className="mt-2 flex flex-wrap gap-2">
              <Button type="button" variant="ghost" onClick={() => void clearRuns()} disabled={clearRunsMutation.isPending}>
                {clearRunsMutation.isPending ? "Clearing..." : "Clear"}
              </Button>
              <Link href={`/projects/${pid}/workspace`} className="text-xs">Workspace</Link>
            </div>
          </CollapsibleSection>

          <CollapsibleSection title="Project Wiki" defaultOpen={!activeRunId}>
            <WikiQuickAccess projectId={pid} />
          </CollapsibleSection>
          </div>
        </aside>
      </section>
    </main>
  );
}
