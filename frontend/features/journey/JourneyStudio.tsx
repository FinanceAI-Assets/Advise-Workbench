"use client";

import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { ActivityTodoList } from "@/components/activity/ActivityTodoList";
import { DocumentUploader } from "@/components/documents/DocumentUploader";
import { ZonePanelErrorBoundary } from "@/components/ErrorBoundary";
import { ApprovalBanner } from "@/components/run-studio/ApprovalBanner";
import { EvidenceClaimsPanel } from "@/components/run-studio/EvidenceClaimsPanel";
import { RunHealthPanel } from "@/components/run-studio/RunHealthPanel";
import { ToolActivityFeed } from "@/components/run-studio/ToolActivityFeed";
import { ZoneAInstruction } from "@/components/run-studio/ZoneAInstruction";
import { ZoneCLiveMonitor } from "@/components/run-studio/ZoneCLiveMonitor";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { WikiQuickAccess } from "@/components/wiki/WikiQuickAccess";
import { useProjectStudio, type ProjectStudio } from "@/hooks/useProjectStudio";
import { formatCostCompact, formatTokenCount } from "@/lib/formatTokens";

import { isStepId, stepStates, STEPS, suggestedStep, type JourneyFacts, type StepId, type StepState } from "./steps";

const FORMATS = [
  { id: "pptx", label: "Presentation (PPTX)" },
  { id: "docx", label: "Word document (DOCX)" },
  { id: "xlsx", label: "Spreadsheet (XLSX)" },
  { id: "pdf", label: "PDF report" },
  { id: "process_map", label: "Process map (draw.io)" },
] as const;

const STATE_LABEL: Record<StepState, string> = {
  done: "Done",
  current: "Now",
  attention: "Needs attention",
  todo: "Later",
};

const STATE_STYLE: Record<StepState, string> = {
  done: "border-[var(--success)] bg-[var(--success-light)] text-[var(--text-primary)]",
  current: "border-[var(--accent-blue)] bg-white text-[var(--text-primary)]",
  attention: "border-[var(--warning)] bg-[var(--warning-light)] text-[var(--text-primary)]",
  todo: "border-[var(--surface-border)] bg-[var(--surface-muted)] text-[var(--text-muted)]",
};

type Props = {
  pid: string;
  initialRunId?: string | null;
};

export function JourneyStudio({ pid, initialRunId = null }: Props) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const studio = useProjectStudio({ pid, initialRunId });
  const { api, token, ready, hydrated } = studio;

  const documents = useQuery({
    queryKey: ["journey-documents", pid],
    enabled: Boolean(token && pid),
    refetchInterval: 15_000,
    queryFn: async () => {
      const res = await api(`/api/documents/list?project_id=${encodeURIComponent(pid)}`);
      const data = (await res.json().catch(() => ({}))) as { items?: string[] };
      return res.ok && Array.isArray(data.items) ? data.items : [];
    },
  });

  // Follow the newest run unless the user picked one.
  const runs = studio.runsQuery.data ?? [];
  const newestRunId = runs[0]?.id ?? null;
  const { activeRunId, setActiveRunId } = studio;
  useEffect(() => {
    if (!activeRunId && newestRunId) setActiveRunId(newestRunId);
  }, [activeRunId, newestRunId, setActiveRunId]);

  const facts: JourneyFacts = useMemo(
    () => ({
      userMessages: studio.activeMessages.filter((m) => m.role === "user").length,
      documents: documents.data?.length ?? 0,
      planReady: Boolean(studio.planHash) && studio.activeOpenQuestions.length === 0,
      openQuestions: studio.activeOpenQuestions.length,
      hasRun: Boolean(activeRunId),
      runStatus: activeRunId ? studio.runStatus || studio.activeRun?.status || "" : "",
    }),
    [studio.activeMessages, documents.data, studio.planHash, studio.activeOpenQuestions, activeRunId, studio.runStatus, studio.activeRun],
  );
  const states = useMemo(() => stepStates(facts), [facts]);
  const suggested = suggestedStep(facts);

  const requested = searchParams.get("step");
  const step: StepId = isStepId(requested) ? requested : suggested;
  const goTo = (next: StepId) => {
    const params = new URLSearchParams(searchParams.toString());
    params.set("step", next);
    router.replace(`${pathname}?${params.toString()}`, { scroll: false });
  };

  const [sheldonOpen, setSheldonOpen] = useState(false);

  if (!hydrated || !ready || !token) {
    return (
      <main style={{ padding: 24 }}>
        <p>Redirecting…</p>
      </main>
    );
  }

  const current = STEPS.find((s) => s.id === step) ?? STEPS[0];
  const index = STEPS.findIndex((s) => s.id === step);
  const busy = studio.isLive || studio.activeChatBusy;

  return (
    <main className="space-y-4">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold">Project {pid}</h1>
          <p className="text-xs text-[var(--text-muted)]">
            Guided view ·{" "}
            <Link href={`/projects/${pid}`} className="underline">
              Switch to the classic view
            </Link>
          </p>
        </div>
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 border border-[var(--surface-border)] bg-white px-3 py-1.5 text-xs">
            <span className="text-[var(--text-muted)]">Session</span>
            <span className="font-mono font-medium">{formatTokenCount(studio.sessionTokens)} tok</span>
            <span className="text-[var(--text-muted)]">·</span>
            <span className="font-mono font-semibold text-[var(--accent-blue)]">{studio.sessionCostLabel}</span>
            {busy ? <span className="text-[var(--accent-blue)]">working…</span> : null}
          </div>
          <Button type="button" variant="ghost" onClick={studio.logout}>
            Sign out
          </Button>
        </div>
      </header>

      <nav aria-label="Project steps">
        <ol className="grid gap-2 sm:grid-cols-3 lg:grid-cols-6">
          {STEPS.map((s, i) => {
            const info = states[s.id];
            const selected = s.id === step;
            return (
              <li key={s.id}>
                <Button
                  type="button"
                  variant="ghost"
                  onClick={() => goTo(s.id)}
                  aria-current={selected ? "step" : undefined}
                  title={info.hint}
                  className={`flex min-h-16 w-full flex-col items-start gap-1 border-2 px-3 py-2 text-left ${STATE_STYLE[info.state]} ${
                    selected ? "outline outline-2 outline-offset-2 outline-[var(--accent-blue)]" : ""
                  }`}
                >
                  <span className="text-sm font-semibold">
                    {i + 1}. {s.label}
                  </span>
                  <span className="text-2xs uppercase tracking-wide">{STATE_LABEL[info.state]}</span>
                </Button>
              </li>
            );
          })}
        </ol>
      </nav>

      <section className="border border-[var(--surface-border)] bg-white p-3">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <h2 className="text-lg font-semibold">
              Step {index + 1}: {current.label}
            </h2>
            <p className="text-sm text-[var(--text-muted)]">{current.purpose}</p>
            <p className="mt-1 text-sm" role="status">
              {states[step].hint}
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            {step !== suggested ? (
              <Button type="button" variant="secondary" onClick={() => goTo(suggested)}>
                Go to {STEPS.find((s) => s.id === suggested)?.label}
              </Button>
            ) : null}
            {step !== "brief" ? (
              <Button type="button" variant="ghost" onClick={() => setSheldonOpen((open) => !open)} aria-expanded={sheldonOpen}>
                {sheldonOpen ? "Hide Sheldon" : "Ask Sheldon"}
              </Button>
            ) : null}
          </div>
        </div>
      </section>

      {studio.error ? <div className="alert alert--error p-2 text-sm">{studio.error}</div> : null}
      {studio.activeChatBusy ? (
        <p className="border border-[var(--surface-border)] bg-[var(--surface-muted)] p-2 text-sm" role="status">
          Sheldon is working. A reply can take one to two minutes; if this page reports a timeout, wait and refresh instead of
          sending the message again.
        </p>
      ) : null}

      <div className={sheldonOpen && step !== "brief" ? "grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(320px,420px)]" : ""}>
        <div className="min-w-0 space-y-4">
          {step === "brief" ? <SheldonChat pid={pid} studio={studio} /> : null}
          {step === "sources" ? <SourcesStep pid={pid} count={facts.documents} /> : null}
          {step === "plan" ? <PlanStep pid={pid} studio={studio} facts={facts} onBuilt={() => goTo("build")} /> : null}
          {step === "build" ? <BuildStep pid={pid} studio={studio} /> : null}
          {step === "review" ? <ReviewStep pid={pid} studio={studio} facts={facts} /> : null}
          {step === "deliver" ? <DeliverStep pid={pid} studio={studio} /> : null}
        </div>
        {sheldonOpen && step !== "brief" ? (
          <aside aria-label="Sheldon">
            <SheldonChat pid={pid} studio={studio} />
          </aside>
        ) : null}
      </div>
    </main>
  );
}

function SheldonChat({ pid, studio }: { pid: string; studio: ProjectStudio }) {
  const run = studio.studio;
  const { activeRunId, cowork } = studio;
  return (
    <>
      {studio.chatPhase ? (
        <p role="status" className="px-3 py-1 text-xs text-[var(--text-muted)]">Sheldon: {studio.chatPhase}…</p>
      ) : null}
      <ZonePanelErrorBoundary label="Instruction chat">
        <ZoneAInstruction
          projectId={pid}
          recommendationNote={activeRunId ? run.recommendationNote : null}
          chatMessages={studio.activeMessages}
          chatInput={activeRunId ? run.chatInput : studio.chatInput}
          setChatInput={activeRunId ? run.setChatInput : studio.setChatInput}
          chatBusy={studio.activeChatBusy}
          onSendChat={activeRunId ? run.sendChatMessage : studio.sendMessage}
          conversationId={studio.activeConversationId}
          openQuestions={studio.activeOpenQuestions}
          decisionPrompts={studio.activeDecisionPrompts}
          unresolvedPromptIds={studio.activeUnresolvedPromptIds}
          onSubmitDecisions={activeRunId ? run.submitDecisionAnswers : studio.submitDecisionAnswers}
          decisionBusy={activeRunId ? run.decisionBusy : studio.decisionBusy}
          onUpdateOutline={activeRunId ? run.updateConversationOutline : studio.updateOutline}
          thinkingStatements={cowork.thinkingStatements}
          hasThinkingTrace={cowork.hasThinkingTrace}
          thinkingTrace={cowork.thinkingTrace}
          thinkingExpanded={cowork.thinkingExpanded}
          onToggleThinkingTrace={() => cowork.setThinkingExpanded((prev) => !prev)}
        />
      </ZonePanelErrorBoundary>
    </>
  );
}

function SourcesStep({ pid, count }: { pid: string; count: number }) {
  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <Card className="space-y-2 p-3">
        <h3 className="text-sm font-semibold">Project documents ({count})</h3>
        <p className="text-xs text-[var(--text-muted)]">
          Accepted: .txt, .md, .csv, .json, .pdf, .docx, .pptx, .xlsx, .xls, up to 50 MB each. Figures in the deliverable are
          expected to come from these files.
        </p>
        <DocumentUploader projectId={pid} />
      </Card>
      <Card className="space-y-2 p-3">
        <h3 className="text-sm font-semibold">Project wiki</h3>
        <p className="text-xs text-[var(--text-muted)]">Knowledge built from the documents, runs and chats of this project.</p>
        <WikiQuickAccess projectId={pid} />
      </Card>
    </div>
  );
}

function PlanStep({ pid, studio, facts, onBuilt }: { pid: string; studio: ProjectStudio; facts: JourneyFacts; onBuilt: () => void }) {
  const [formats, setFormats] = useState<string[]>([]);
  const outline = studio.agreedDecisions;
  const canConfirm = !facts.hasRun && facts.userMessages > 0 && formats.length > 0 && !studio.activeChatBusy;

  const toggle = (id: string) => setFormats((prev) => (prev.includes(id) ? prev.filter((f) => f !== id) : [...prev, id]));
  const confirm = async () => {
    const labels = FORMATS.filter((f) => formats.includes(f.id)).map((f) => f.label);
    await studio.sendText(
      `Confirmed. Deliverable format: ${labels.join(" and ")} only. Do not produce any other format. ` +
        `Put a (source: document name) citation next to every figure. Build it.`,
    );
    onBuilt();
  };

  return (
    <div className="space-y-4">
      {facts.hasRun ? (
        <>
          <p className="text-sm">The plan was confirmed and a run exists. Its approval state is shown below.</p>
          <ApprovalBanner state={studio.studio.approvalBannerState} />
        </>
      ) : null}

      <Card className="space-y-2 p-3">
        <h3 className="text-sm font-semibold">Outline agreed with Sheldon</h3>
        {outline.length > 0 ? (
          <ol className="space-y-1 text-sm">
            {outline.map((item) => (
              <li key={`${item.slide_num}-${item.title}`}>
                <span className="font-medium">
                  {item.slide_num}. {item.title}
                </span>
                {item.key_message ? <span className="text-[var(--text-muted)]"> — {item.key_message}</span> : null}
              </li>
            ))}
          </ol>
        ) : null}
        {outline.length > 0 ? (
          <p className="text-sm text-[var(--text-muted)]">
            To change titles or the order, open Ask Sheldon and use “Edit outline” under the plan, then save.
          </p>
        ) : (
          <EmptyState title="No outline yet" description="Agree the storyline and sections with Sheldon in the Brief step." />
        )}
        {studio.activeOpenQuestions.length > 0 ? (
          <div>
            <h4 className="text-xs font-semibold uppercase tracking-wide text-[var(--text-muted)]">Open questions</h4>
            <ul className="list-disc pl-5 text-sm">
              {studio.activeOpenQuestions.map((q) => (
                <li key={q}>{q}</li>
              ))}
            </ul>
          </div>
        ) : null}
      </Card>

      {!facts.hasRun ? (
        <Card className="space-y-3 p-3">
          <h3 className="text-sm font-semibold">Deliverable format</h3>
          <p className="text-xs text-[var(--text-muted)]">
            Choose here, not in the chat: the format you tick is sent to Sheldon as an explicit instruction with the confirmation.
          </p>
          <div className="grid gap-2 sm:grid-cols-2" role="group" aria-label="Deliverable format">
            {FORMATS.map((f) => {
              const chosen = formats.includes(f.id);
              return (
                <Button
                  key={f.id}
                  type="button"
                  variant="secondary"
                  aria-pressed={chosen}
                  onClick={() => toggle(f.id)}
                  className={`min-h-11 text-left ${chosen ? "border-[var(--success)] bg-[var(--success-light)] font-semibold" : ""}`}
                >
                  {chosen ? "✓ " : ""}
                  {f.label}
                </Button>
              );
            })}
          </div>
          {facts.documents === 0 ? (
            <p className="alert alert--warning p-2 text-sm">No source documents are uploaded. Figures in the deliverable cannot be cited without them.</p>
          ) : null}
          <div className="flex flex-wrap items-center gap-3">
            <Button type="button" onClick={() => void confirm()} disabled={!canConfirm}>
              {studio.activeChatBusy ? "Sending…" : "Confirm plan and build"}
            </Button>
            <span className="text-xs text-[var(--text-muted)]">
              {facts.userMessages === 0
                ? "Describe the deliverable in the Brief step first."
                : formats.length === 0
                  ? "Tick at least one format."
                  : "Starts the run. Generation usually takes 10 to 20 minutes."}
            </span>
          </div>
        </Card>
      ) : null}
      <p className="text-xs text-[var(--text-muted)]">
        <Link href={`/projects/${pid}/settings/formats`} className="underline">
          Output format settings
        </Link>
      </p>
    </div>
  );
}

function RunFeed({ pid, studio }: { pid: string; studio: ProjectStudio }) {
  const run = studio.studio;
  return (
    <ZonePanelErrorBoundary label="Activity feed">
      <ToolActivityFeed
        events={studio.events}
        parsedEvents={studio.parsedEvents}
        runChecklistTodos={run.runChecklistTodos}
        artifacts={run.artifacts}
        pollMode={studio.pollMode}
        streamError={studio.streamError}
        downloadsContent={run.downloadsContent}
        onTaskAction={run.applyTaskAction}
        onRegenerateSlide={run.regenerateSlide}
        onPatchSlideElement={run.patchSlideElement}
        slideRegenerateBusyIndex={run.slideRegenerateBusyIndex}
        hooksPanel={run.hooksPanel}
        permissionPanel={run.permissionPanel}
        projectId={pid}
        runId={studio.activeRunId ?? undefined}
        agreedDecisions={studio.agreedDecisions}
      />
    </ZonePanelErrorBoundary>
  );
}

function BuildStep({ pid, studio }: { pid: string; studio: ProjectStudio }) {
  const run = studio.studio;
  if (!studio.activeRunId) {
    return <EmptyState title="No run yet" description="Confirm the plan in the Plan step to start the build." />;
  }
  return (
    <div className="space-y-4">
      <Card className="space-y-2 p-3">
        <h3 className="text-sm font-semibold">Run health</h3>
        <RunHealthPanel projectId={pid} onSelectRun={(runId) => studio.setActiveRunId(runId)} />
      </Card>
      <Card className="space-y-2 p-3">
        <h3 className="text-sm font-semibold">Steps</h3>
        <ActivityTodoList projectId={pid} onTodoClick={(runId) => studio.setActiveRunId(runId)} maxItems={10} />
      </Card>
      <Card className="space-y-2 p-3">
        <h3 className="text-sm font-semibold">Live progress and controls</h3>
        <ZonePanelErrorBoundary label="Execution audit trail">
          <ZoneCLiveMonitor
            events={studio.events}
            showAgentGraph={false}
            runControls={run.runControls}
            evaluatorSummary={
              run.evaluatorSummary
                ? {
                    qaPassed: Boolean(run.evaluatorSummary.qa_passed),
                    visualQaPassed: Boolean(run.evaluatorSummary.visual_qa_passed),
                    guardrailsPassed: Boolean(run.evaluatorSummary.guardrails_passed),
                    status: run.evaluatorSummary.status,
                  }
                : null
            }
          />
        </ZonePanelErrorBoundary>
      </Card>
      <RunFeed pid={pid} studio={studio} />
    </div>
  );
}

function ReviewStep({ pid, studio, facts }: { pid: string; studio: ProjectStudio; facts: JourneyFacts }) {
  const run = studio.studio;
  if (!studio.activeRunId) {
    return <EmptyState title="Nothing to review yet" description="A run appears here when the build finishes." />;
  }
  const summary = run.evaluatorSummary;
  const checks: Array<[string, boolean | undefined]> = summary
    ? [
        ["Content quality", Boolean(summary.qa_passed)],
        ["Visual quality", Boolean(summary.visual_qa_passed)],
        ["Guardrails", Boolean(summary.guardrails_passed)],
      ]
    : [];
  // The runs list has no failure text; the run's own "failed" event carries the reason.
  const failedEvent = [...studio.parsedEvents].reverse().find((e) => e.eventType === "failed");
  const failure =
    facts.runStatus === "failed"
      ? typeof failedEvent?.payload.error === "string"
        ? failedEvent.payload.error
        : "The run failed. Open the activity feed below for the last events."
      : null;
  return (
    <div className="space-y-4">
      {failure ? (
        <Card className="space-y-2 border-[var(--warning)] p-3">
          <h3 className="text-sm font-semibold">Why the run failed</h3>
          <p className="text-sm">{failure}</p>
          <p className="text-sm text-[var(--text-muted)]">
            Next: adjust the request in the Brief step (for example, ask for a source citation next to every figure) and confirm a
            new plan. A failed run cannot be resumed.
          </p>
        </Card>
      ) : null}
      <ApprovalBanner state={run.approvalBannerState} />
      {checks.length > 0 ? (
        <Card className="space-y-2 p-3">
          <h3 className="text-sm font-semibold">Checks</h3>
          <ul className="grid gap-2 sm:grid-cols-3">
            {checks.map(([label, passed]) => (
              <li key={label} className={`border px-3 py-2 text-sm ${passed ? "border-[var(--success)] bg-[var(--success-light)]" : "border-[var(--warning)] bg-[var(--warning-light)]"}`}>
                <span className="font-medium">{label}</span>: {passed ? "passed" : "did not pass"}
              </li>
            ))}
          </ul>
        </Card>
      ) : null}
      <Card className="space-y-2 p-3">
        <h3 className="text-sm font-semibold">Evidence for the figures</h3>
        <p className="text-sm text-[var(--text-muted)]">Accept or reject each claim before you approve the deliverable.</p>
        <EvidenceClaimsPanel projectId={pid} runId={studio.activeRunId} enabled={facts.runStatus !== "running"} />
      </Card>
      <RunFeed pid={pid} studio={studio} />
    </div>
  );
}

function DeliverStep({ pid, studio }: { pid: string; studio: ProjectStudio }) {
  const runs = studio.runsQuery.data ?? [];
  return (
    <div className="space-y-4">
      <Card className="space-y-2 p-3">
        <h3 className="text-sm font-semibold">Files</h3>
        {studio.activeRunId ? (
          studio.studio.downloadsContent ?? <p className="text-sm text-[var(--text-muted)]">No files are available for this run yet.</p>
        ) : (
          <EmptyState title="No run selected" description="Files appear here after a run is approved." />
        )}
      </Card>
      <Card className="space-y-2 p-3">
        <h3 className="text-sm font-semibold">Runs in this project</h3>
        {runs.length === 0 ? (
          <EmptyState title="No runs yet" description="Runs are listed here once a plan is confirmed." />
        ) : (
          <ul className="space-y-1">
            {runs.map((r) => {
              const tokens = (r.tokens_input ?? 0) + (r.tokens_output ?? 0) + (r.tokens_cache_read ?? 0) + (r.tokens_cache_creation ?? 0);
              const cost = formatCostCompact(r.cost_usd);
              return (
                <li key={r.id}>
                  <Button
                    type="button"
                    variant="ghost"
                    onClick={() => studio.setActiveRunId(r.id)}
                    aria-pressed={studio.activeRunId === r.id}
                    className={`flex min-h-11 w-full items-center justify-between gap-3 border px-3 text-left text-sm ${
                      studio.activeRunId === r.id ? "border-[var(--accent-blue)]" : "border-[var(--surface-border)]"
                    }`}
                  >
                    <span className="truncate font-mono">{r.id}</span>
                    <span>{r.status}</span>
                    <span className="text-xs text-[var(--text-muted)]">
                      {tokens > 0 ? `${formatTokenCount(tokens)} tok` : ""}
                      {tokens > 0 && cost ? " · " : ""}
                      {cost}
                    </span>
                  </Button>
                </li>
              );
            })}
          </ul>
        )}
        <p className="text-xs">
          <Link href={`/projects/${pid}/workspace`} className="underline">
            Open the project workspace
          </Link>
        </p>
      </Card>
    </div>
  );
}
