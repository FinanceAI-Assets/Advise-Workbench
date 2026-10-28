"use client";

import { FileText, Sparkles, X } from "lucide-react";
import { type FormEvent, type ReactNode, useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { type LibraryAnswer, useLibraryAskMutation } from "@/hooks/useWorkbench";
import { cn } from "@/lib/utils";

const SUGGESTIONS = [
  "Summarize the library",
  "Show category distribution",
  "Show maturity breakdown",
  "Which practices were updated recently?",
  "Show my saved practices",
  "Who owns the practices?",
  "List the source documents",
];

type Turn = { id: number; question: string; answer?: LibraryAnswer; error?: string };

function AssistantAvatar() {
  return (
    <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-[var(--primary-950)] text-[var(--accent-green)]">
      <Sparkles size={14} aria-hidden />
    </span>
  );
}

/** One chat bubble, styled like the engagement conversation: yours on the right, the assistant's on the left. */
function Bubble({ mine, children }: { mine: boolean; children: ReactNode }) {
  return (
    <div className={cn("flex items-end gap-2", mine ? "justify-end" : "justify-start")}>
      {mine ? null : <AssistantAvatar />}
      <div
        className={cn(
          "rounded-2xl px-4 py-2.5 text-sm text-[var(--text-default)] shadow-sm",
          mine
            ? "max-w-[85%] rounded-br-sm bg-[#DCF1C2]"
            : "min-w-0 max-w-[88%] rounded-bl-sm border border-[var(--surface-border)] bg-white"
        )}
      >
        {mine ? null : <p className="mb-1 text-xs font-semibold text-[var(--accent-green-dark)]">Library assistant</p>}
        <div className="break-words leading-relaxed">{children}</div>
      </div>
    </div>
  );
}

function AnswerBody({ answer, onOpenPractice }: { answer: LibraryAnswer; onOpenPractice: (id: string) => void }) {
  return (
    <div className="space-y-3">
      <p className="whitespace-pre-line">{answer.answer}</p>
      {answer.documents.length ? (
        <ul className="space-y-1.5 border-t border-[var(--surface-border)] pt-2">
          {answer.documents.map((doc) => (
            <li key={`${doc.practiceId}:${doc.filename}`} className="flex items-start gap-2 text-xs text-[var(--text-muted)]">
              <FileText size={14} className="mt-0.5 shrink-0 text-[var(--accent-green-dark)]" aria-hidden />
              <span>
                <span className="font-medium text-[var(--text-default)]">{doc.filename}</span> · {doc.practice}
              </span>
            </li>
          ))}
        </ul>
      ) : null}
      {answer.sources.length ? (
        <ol className="space-y-1.5 border-l-2 border-[var(--accent-green)] pl-3">
          {answer.sources.map((source, n) => (
            <li key={`${source.source}:${n}`} className="text-xs text-[var(--text-muted)]">
              <span className="font-semibold text-[var(--text-default)]">[{n + 1}] {source.heading || source.source}</span>
              {source.text ? <span className="block line-clamp-2">{source.text}</span> : null}
            </li>
          ))}
        </ol>
      ) : null}
      {answer.practices.length ? (
        <div className="flex flex-wrap gap-1.5">
          {answer.practices.map((practice) => (
            <button
              key={practice.id}
              type="button"
              onClick={() => onOpenPractice(practice.id)}
              title={practice.category}
              className="rounded-md border border-[var(--surface-border)] bg-[#EFF6E6] px-2 py-1 text-left text-2xs font-medium text-[#356B12] transition hover:border-[var(--accent-green)]"
            >
              {practice.id.toUpperCase()} · {practice.title}
            </button>
          ))}
        </div>
      ) : null}
    </div>
  );
}

/** Right-edge sidebar, drawn over the page without moving it, that answers questions from the approved Leading Practice catalog and its source documents. */
export function LibraryAssistant({ onClose, onOpenPractice }: { onClose: () => void; onOpenPractice: (id: string) => void }) {
  const ask = useLibraryAskMutation();
  const [question, setQuestion] = useState("");
  const [turns, setTurns] = useState<Turn[]>([]);
  const bottom = useRef<HTMLDivElement>(null);
  const nextId = useRef(0);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  useEffect(() => {
    bottom.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [turns]);

  const send = (text: string) => {
    const q = text.trim();
    if (!q || ask.isPending) return;
    const id = ++nextId.current;
    setTurns((prev) => [...prev, { id, question: q }]);
    setQuestion("");
    ask.mutate(q, {
      onSuccess: (answer) => setTurns((prev) => prev.map((t) => (t.id === id ? { ...t, answer } : t))),
      onError: (error) => setTurns((prev) => prev.map((t) => (t.id === id ? { ...t, error: error.message } : t))),
    });
  };

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    send(question);
  };

  return (
    <aside
      aria-label="Ask the Library"
      className="fixed bottom-0 right-0 top-14 z-30 flex w-full flex-col border-l border-[var(--surface-border)] bg-[var(--alabaster)] shadow-[var(--shadow-xl)] sm:w-[420px]"
    >
      <header className="flex items-start justify-between gap-3 border-b border-[var(--surface-border)] bg-white px-4 py-4">
        <div className="flex items-center gap-3">
          <AssistantAvatar />
          <div>
            <p className="text-2xs font-semibold uppercase tracking-wide text-[var(--accent-green-dark)]">Leading practice assistant</p>
            <h2 className="text-base font-semibold text-[var(--text-default)]">Ask the Library</h2>
          </div>
        </div>
        <button
          type="button"
          onClick={onClose}
          aria-label="Close"
          className="flex h-9 w-9 items-center justify-center rounded-md border border-[var(--surface-border)] bg-white text-[var(--coral-black)] transition hover:bg-[var(--primary-50)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--coral-black)]"
        >
          <X size={16} aria-hidden />
        </button>
      </header>

      <div className="flex-1 space-y-4 overflow-y-auto px-4 py-4">
        <div className="rounded-lg border border-[var(--surface-border)] bg-[#EFF6E6] p-3 text-xs leading-relaxed text-[var(--text-muted)]">
          <span className="font-semibold text-[#356B12]">Ask the Library:</span> questions are answered from the approved
          practice catalog and its source documents. You can ask about counts, categories, maturity, owners, recent updates,
          your saved practices, source documents, or what a practice recommends.
        </div>

        <div className="flex flex-wrap gap-2">
          {SUGGESTIONS.map((s) => (
            <button
              key={s}
              type="button"
              disabled={ask.isPending}
              onClick={() => send(s)}
              className="rounded-md border border-[var(--surface-border)] bg-white px-3 py-1.5 text-xs text-[var(--text-muted)] transition hover:border-[var(--accent-green)] hover:text-[var(--accent-green-dark)] disabled:cursor-not-allowed disabled:opacity-60"
            >
              {s}
            </button>
          ))}
        </div>

        {turns.map((turn) => (
          <div key={turn.id} className="space-y-3">
            <Bubble mine>{turn.question}</Bubble>
            <Bubble mine={false}>
              {turn.answer ? (
                <AnswerBody answer={turn.answer} onOpenPractice={onOpenPractice} />
              ) : turn.error ? (
                <p className="text-[var(--status-failed-text)]">{turn.error}</p>
              ) : (
                <p className="animate-pulse text-[var(--text-muted)]">Searching the library…</p>
              )}
            </Bubble>
          </div>
        ))}
        <div ref={bottom} />
      </div>

      <form onSubmit={onSubmit} className="space-y-2 border-t border-[var(--surface-border)] bg-white px-4 py-3">
        <div className="flex items-start gap-2">
          <Input
            autoFocus
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            maxLength={500}
            placeholder="Ask about practices, categories or documents"
            aria-label="Question"
          />
          <Button type="submit" disabled={!question.trim() || ask.isPending} className="shrink-0">
            {ask.isPending ? "Asking…" : "Ask"}
          </Button>
        </div>
        <p className="text-2xs text-[var(--text-muted)]">Answers cite approved practices only. Verify before sharing.</p>
      </form>
    </aside>
  );
}
