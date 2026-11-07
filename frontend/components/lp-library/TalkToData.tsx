"use client";

import { Check, CheckCircle2, Plus, Search, Send, X } from "lucide-react";
import { useRouter } from "next/navigation";
import { type FormEvent, type KeyboardEvent, useEffect, useRef, useState } from "react";

import { AddResultNote, engagementSourcesPath } from "@/components/lp-library/AddResultNote";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Select } from "@/components/ui/Select";
import { Textarea } from "@/components/ui/Textarea";
import {
  type LibraryAnswer,
  useAddPracticesToEngagementMutation,
  useLibraryAskMutation,
  useMyEngagementOptionsQuery,
  usePracticeQuery,
} from "@/hooks/useWorkbench";
import { useAuth } from "@/lib/auth-context";
import { cn } from "@/lib/utils";

/** A source the user checked in library chat; only these move into an engagement. */
export type SelectedSource = {
  practiceId: string;
  code: string;
  title: string;
  section: string;
  passage: string;
  version: string;
  owner: string;
  approved: string;
};

export type DiscoveryTurn = {
  id: number;
  question: string;
  scope: "broad" | "selected";
  at: string;
  answer?: LibraryAnswer;
  error?: string;
};

type Source = LibraryAnswer["sources"][number];

const MAX_MATCHES = 6;

const clock = () => new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });

/** "Operating model playbook · Sequencing" → ["Operating model playbook", "Sequencing"]. */
function splitHeading(heading: string): [string, string] {
  const at = heading.lastIndexOf(" · ");
  return at > 0 ? [heading.slice(0, at), heading.slice(at + 3)] : [heading, ""];
}

/** The passage numbers an answer cites, in order: "… [1] … [3][4]" → [1, 3, 4]. */
function cited(answer: string): number[] {
  const numbers = Array.from(answer.matchAll(/\[(\d+)\]/g), (m) => Number(m[1]));
  return Array.from(new Set(numbers)).sort((a, b) => a - b);
}

function listOf(items: string[]): string {
  return items.length < 2 ? items.join("") : `${items.slice(0, -1).join(", ")} and ${items[items.length - 1]}`;
}

function SourceCard({
  n,
  source,
  checked,
  onToggle,
}: {
  n: number;
  source: Source;
  checked: boolean;
  onToggle: (selected: SelectedSource) => void;
}) {
  const practice = usePracticeQuery(source.practiceId);
  const detail = practice.data;
  const [headingTitle, section] = splitHeading(source.heading || source.source);
  const selectable = Boolean(source.practiceId && detail);
  const code = detail?.code || source.practiceId.toUpperCase();
  const title = detail?.title || headingTitle;

  const toggle = () =>
    detail &&
    onToggle({
      practiceId: source.practiceId,
      code,
      title,
      section,
      passage: source.text,
      version: detail.versionLabel,
      owner: [detail.sourceAttribution, detail.practiceOwner].filter(Boolean).join(" · "),
      approved: detail.approvedMeta,
    });

  return (
    <label
      className={cn(
        "flex h-full cursor-pointer flex-col gap-2 rounded-lg border bg-white p-3 text-left shadow-sm transition",
        checked ? "border-[var(--accent-green)] ring-1 ring-[var(--accent-green)]" : "border-[var(--surface-border)]",
        !selectable && "cursor-not-allowed opacity-80"
      )}
      title={selectable ? undefined : "Not an approved practice, so it cannot be taken into an engagement"}
    >
      <span className="flex items-start gap-2">
        <input
          type="checkbox"
          className="mt-0.5 h-4 w-4 shrink-0 accent-[var(--accent-green)]"
          checked={checked}
          disabled={!selectable}
          onChange={toggle}
        />
        <span className="text-sm font-semibold leading-snug text-[var(--text-default)]">{title}</span>
      </span>
      <span className="text-2xs text-[var(--text-muted)]">
        [{n}] {source.practiceId ? code : "Library file"}
        {detail?.versionLabel ? ` · ${detail.versionLabel}` : ""}
        {section ? ` · ${section}` : ""}
      </span>
      <span className="line-clamp-3 text-xs leading-relaxed text-[var(--text-default)]">&ldquo;{source.text}&rdquo;</span>
      <span className="mt-auto text-2xs text-[var(--text-muted)]">
        {detail ? (
          <>
            {[detail.sourceAttribution, detail.practiceOwner].filter(Boolean).join(" · ")}
            <span className="block">{detail.approvedMeta}</span>
          </>
        ) : source.practiceId ? (
          practice.isPending ? "Loading practice…" : "Practice details unavailable"
        ) : (
          "Library file outside the approved catalog"
        )}
      </span>
    </label>
  );
}

function AnswerTurn({ turn, author }: { turn: DiscoveryTurn; author: string }) {
  const numbers = turn.answer ? cited(turn.answer.answer) : [];
  return (
    <div className="space-y-3">
      <div className="rounded-lg bg-[var(--alabaster)] px-3 py-2.5">
        <p className="text-2xs text-[var(--text-muted)]">
          {author} · {turn.at}
          {turn.scope === "selected" ? " · Selected sources only" : ""}
        </p>
        <p className="mt-1 text-sm text-[var(--text-default)]">{turn.question}</p>
      </div>
      <div className="px-1">
        <div className="flex items-center justify-between gap-2">
          <p className="text-2xs font-semibold text-[var(--text-default)]">Advise · {turn.at}</p>
          {turn.answer?.sources.length ? (
            <span className="rounded-md bg-[#EFF6E6] px-2 py-0.5 text-2xs font-medium text-[#356B12]">Cited answer</span>
          ) : null}
        </div>
        {turn.answer ? (
          <>
            <p className="mt-1.5 whitespace-pre-line text-sm leading-relaxed text-[var(--text-default)]">{turn.answer.answer}</p>
            {numbers.length ? (
              <p className="mt-2 text-xs text-[#356B12]">
                Cited sources: {listOf(numbers.map((n) => `[${n}]`))}. Check the sources at right to take them forward; your
                selection stays visible while you chat.
              </p>
            ) : null}
          </>
        ) : turn.error ? (
          <p className="mt-1.5 text-sm text-[var(--status-failed-text)]">{turn.error}</p>
        ) : (
          <p className="mt-1.5 animate-pulse text-sm text-[var(--text-muted)]">Searching the library…</p>
        )}
      </div>
    </div>
  );
}

/**
 * Library chat: ask the approved library, check the retrieved sources worth keeping, then add the checked ones to an
 * engagement's sources. Checking a source never changes the answers unless "Ask selected sources only" is on.
 */
export function TalkToKnowledge({
  turns,
  setTurns,
  selection,
  onToggle,
  onBrowse,
  chosenScope,
  setScope,
  browsing,
}: {
  turns: DiscoveryTurn[];
  setTurns: (update: (prev: DiscoveryTurn[]) => DiscoveryTurn[]) => void;
  selection: SelectedSource[];
  onToggle: (source: SelectedSource) => void;
  onBrowse: () => void;
  chosenScope: DiscoveryTurn["scope"];
  setScope: (scope: DiscoveryTurn["scope"]) => void;
  browsing: boolean;
}) {
  const ask = useLibraryAskMutation();
  const addPractices = useAddPracticesToEngagementMutation();
  const engagements = useMyEngagementOptionsQuery();
  const router = useRouter();
  const { user } = useAuth();
  const [projectId, setProjectId] = useState("");
  const [question, setQuestion] = useState("");
  const nextId = useRef(turns.length);
  const bottom = useRef<HTMLDivElement>(null);
  const composer = useRef<HTMLFormElement>(null);
  const checkedIds = new Set(selection.map((s) => s.practiceId));
  const latest = [...turns].reverse().find((t) => t.answer);
  const sources = latest?.answer?.sources ?? [];
  const unchecked = sources.filter((s) => !s.practiceId || !checkedIds.has(s.practiceId)).length;
  const author = user?.name || "You";
  const rows = engagements.data?.items ?? [];
  const target = projectId || rows[0]?.id || "";
  const selectionIds = selection.map((s) => s.practiceId);
  // Shown only when something was refused, as all added moves on to the engagement's sources.
  const result = addPractices.variables?.practiceIds.join() === selectionIds.join() ? addPractices.data : undefined;
  const resultProject = addPractices.variables?.projectId ?? "";
  // With nothing checked, "selected sources only" has nothing to search, so discovery is broad again.
  const scope = selection.length ? chosenScope : "broad";

  useEffect(() => {
    bottom.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [turns]);

  // Coming back from the source screen, the next thing to do is ask.
  useEffect(() => {
    if (!browsing) composer.current?.querySelector("textarea")?.focus();
  }, [browsing]);

  const send = () => {
    const q = question.trim();
    if (!q || ask.isPending) return;
    const id = ++nextId.current;
    const only = scope === "selected" ? selection.map((s) => s.practiceId) : undefined;
    setTurns((prev) => [...prev, { id, question: q, scope, at: clock() }]);
    setQuestion("");
    ask.mutate(
      { question: q, practiceIds: only, maxResults: MAX_MATCHES },
      {
        onSuccess: (answer) => setTurns((prev) => prev.map((t) => (t.id === id ? { ...t, answer } : t))),
        onError: (error) => setTurns((prev) => prev.map((t) => (t.id === id ? { ...t, error: error.message } : t))),
      }
    );
  };

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    send();
  };

  const onKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send();
    }
  };

  return (
    <div className="space-y-4">
      <div className={cn("grid gap-4", latest && "lg:grid-cols-[minmax(0,1fr)_minmax(0,1.15fr)]")}>
        <Card className="flex min-h-[560px] flex-col gap-4">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="min-w-0">
              <h2 className="text-base font-semibold text-[var(--text-default)]">Talk to your knowledge</h2>
              <p className="text-2xs text-[var(--text-muted)]">
                Permission-aware retrieval · Approved practices only · External web search off · Discovery, not generation
              </p>
            </div>
            <Button type="button" variant="secondary" onClick={onBrowse} className="flex shrink-0 items-center gap-2">
              <Search size={16} aria-hidden />
              Browse sources
            </Button>
          </div>

          <fieldset className="space-y-1.5">
            <legend className="sr-only">Answer scope</legend>
            <div className="flex flex-wrap gap-2">
              {(
                [
                  ["broad", "Broad discovery"],
                  ["selected", "Ask selected sources only"],
                ] as const
              ).map(([value, label]) => (
                <label
                  key={value}
                  className={cn(
                    "flex cursor-pointer items-center gap-2 rounded-md border px-3 py-1.5 text-xs",
                    scope === value
                      ? "border-[var(--accent-green)] bg-[#EFF6E6] font-semibold text-[#356B12]"
                      : "border-[var(--surface-border)] text-[var(--text-muted)]",
                    value === "selected" && !selection.length && "cursor-not-allowed opacity-60"
                  )}
                >
                  <input
                    type="radio"
                    name="scope"
                    className="accent-[var(--accent-green)]"
                    checked={scope === value}
                    disabled={value === "selected" && !selection.length}
                    onChange={() => setScope(value)}
                  />
                  {label}
                </label>
              ))}
            </div>
            <p className="text-2xs text-[var(--text-muted)]">
              {scope === "broad"
                ? "Searches the approved library. Checking a source does not narrow this chat."
                : `Answers come only from your ${selection.length} checked source${selection.length === 1 ? "" : "s"}.`}
            </p>
          </fieldset>

          <div className="flex-1 space-y-4 overflow-y-auto" aria-live="polite">
            {turns.length === 0 ? (
              <p className="rounded-lg border border-dashed border-[var(--surface-border)] p-4 text-sm text-[var(--text-muted)]">
                {scope === "selected"
                  ? `Ask anything about ${listOf(selection.map((s) => s.title))}. Answers come only from ${selection.length === 1 ? "this source" : "these sources"}.`
                  : "Ask what guidance the library holds, compare approaches, or narrow down the sources to take into an engagement."}
              </p>
            ) : (
              turns.map((turn) => <AnswerTurn key={turn.id} turn={turn} author={author} />)
            )}
            <div ref={bottom} />
          </div>

          <form ref={composer} onSubmit={onSubmit} className="space-y-2">
            <div className="rounded-lg border border-[var(--surface-border)] p-2">
              <Textarea
                rows={2}
                value={question}
                maxLength={500}
                onChange={(e) => setQuestion(e.target.value)}
                onKeyDown={onKeyDown}
                placeholder={
                  scope === "selected"
                    ? `Ask about your ${selection.length} selected source${selection.length === 1 ? "" : "s"}…`
                    : "Ask about practices, compare approaches or refine your search…"
                }
                aria-label="Question"
                className="border-0 px-2 focus:ring-0"
              />
              <div className="flex items-center justify-between gap-2 px-1 pt-1">
                <span className="rounded-md bg-[#EFF6E6] px-2 py-0.5 text-2xs font-medium text-[#356B12]">
                  {scope === "broad" ? "Library discovery" : "Selected sources"}
                </span>
                <Button type="submit" disabled={!question.trim() || ask.isPending} className="flex items-center gap-1.5 px-3 py-1.5">
                  <Send size={14} aria-hidden />
                  {ask.isPending ? "Asking…" : "Send"}
                </Button>
              </div>
            </div>
            <p className="text-2xs text-[var(--text-muted)]">
              AI answers are not validated advice. Check passages and applicability before reuse.
            </p>
          </form>
        </Card>

        {latest ? (
        <div className="space-y-3">
          <div className="flex flex-wrap items-start justify-between gap-2">
            <div>
              <h2 className="text-base font-semibold text-[var(--text-default)]">
                Retrieved sources · {sources.length} match{sources.length === 1 ? "" : "es"}
              </h2>
              <p className="text-2xs text-[var(--text-muted)]">Ranked by relevance · Check independently to include</p>
            </div>
            {selection.length ? (
              <span className="rounded-md bg-[#EFF6E6] px-2 py-0.5 text-2xs font-medium text-[#356B12]">
                {selection.length} checked
              </span>
            ) : null}
          </div>

          {sources.length ? (
            <div className="grid gap-3 sm:grid-cols-2">
              {sources.map((source, i) => (
                <SourceCard
                  key={`${latest?.id}:${i}`}
                  n={i + 1}
                  source={source}
                  checked={Boolean(source.practiceId) && checkedIds.has(source.practiceId)}
                  onToggle={onToggle}
                />
              ))}
            </div>
          ) : (
            <Card className="text-sm text-[var(--text-muted)]">
              This answer cites no library passages. Try naming a practice, topic or outcome.
            </Card>
          )}

          <div className="flex items-start gap-2 rounded-lg border border-[#CFE3B5] bg-[#EFF6E6] p-3">
            <CheckCircle2 size={16} className="mt-0.5 shrink-0 text-[var(--accent-green-dark)]" aria-hidden />
            <div>
              <p className="text-sm font-semibold text-[var(--text-default)]">Selection is separate from discovery</p>
              <p className="text-xs text-[var(--text-muted)]">
                Only checked sources go into an engagement.
                {selection.length
                  ? ` Switch to "Ask selected sources only" to restrict future answers to your ${selection.length} checked source${selection.length === 1 ? "" : "s"}.`
                  : " Check a source to keep it while you keep asking."}
              </p>
            </div>
          </div>
        </div>
        ) : null}
      </div>

      {selection.length || latest ? (
      <div className="flex flex-wrap items-center gap-4 rounded-lg border-2 border-[var(--accent-green)] bg-white p-4 shadow-sm">
        <span className="flex items-center gap-1.5 rounded-md border border-[var(--accent-green)] bg-[#EFF6E6] px-2.5 py-1 text-2xs font-semibold text-[#356B12]">
          <Check size={12} aria-hidden />
          {selection.length} source{selection.length === 1 ? "" : "s"} selected
        </span>
        <div className="min-w-0 flex-1">
          {selection.length ? (
            <ul className="mb-1 flex flex-wrap gap-1.5" aria-label="Selected sources">
              {selection.map((source) => (
                <li
                  key={source.practiceId}
                  className="flex max-w-[280px] items-center gap-1 rounded-full bg-[#EFF6E6] py-0.5 pl-2.5 pr-1 text-2xs font-medium text-[#356B12]"
                >
                  <span className="truncate" title={`${source.code} · ${source.title}`}>
                    {source.code} · {source.title}
                  </span>
                  <button
                    type="button"
                    onClick={() => onToggle(source)}
                    aria-label={`Remove ${source.title}`}
                    className="shrink-0 rounded-full p-0.5 hover:bg-white"
                  >
                    <X size={12} aria-hidden />
                  </button>
                </li>
              ))}
            </ul>
          ) : (
            <p className="truncate text-sm font-medium text-[var(--text-default)]">No sources checked yet</p>
          )}
          <p className="text-2xs text-[var(--text-muted)]">
            {latest ? `${unchecked} unchecked result${unchecked === 1 ? "" : "s"} stay in discovery. ` : ""}
            Adding takes you to the engagement&apos;s sources and opens no conversation.
          </p>
        </div>
        <Select
          aria-label="Engagement"
          value={target}
          onChange={(e) => setProjectId(e.target.value)}
          disabled={!rows.length}
          className="w-auto max-w-[260px]"
        >
          {rows.length ? null : <option value="">{engagements.isPending ? "Loading…" : "No active engagements"}</option>}
          {rows.map((row) => (
            <option key={row.id} value={row.id}>
              {row.name} · {row.code}
            </option>
          ))}
        </Select>
        <Button
          type="button"
          onClick={() =>
            addPractices.mutate(
              { projectId: target, practiceIds: selectionIds },
              {
                onSuccess: ({ failed }, { projectId: added }) => {
                  if (!failed.length) router.push(engagementSourcesPath(added));
                },
              }
            )
          }
          disabled={!selection.length || !target || addPractices.isPending}
          className="flex items-center gap-2"
        >
          <Plus size={16} aria-hidden />
          {addPractices.isPending ? "Adding…" : "Add to engagement"}
        </Button>
        {result ? (
          <div className="basis-full space-y-1">
            <AddResultNote
              result={result}
              projectId={resultProject}
              projectName={rows.find((row) => row.id === resultProject)?.name ?? "the engagement"}
              failedHint="Not added:"
            />
          </div>
        ) : null}
      </div>
      ) : null}
    </div>
  );
}

// Backward-compatible alias during UI naming transition.
export const TalkToData = TalkToKnowledge;
