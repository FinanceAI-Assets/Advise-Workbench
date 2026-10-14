"use client";

import { Copy, Sparkles } from "lucide-react";
import { Fragment, useEffect, useMemo, useRef, useState } from "react";

import { ReplyOptions, type ReplyHandlers, hasReplyOptions } from "@/components/conversation/ReplyOptions";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { cn } from "@/lib/utils";
import type { ConversationMessage } from "@/types/api";

/** Render `**bold**` and line breaks from the assistant's reply as text (never as HTML). */
function FormattedText({ text }: { text: string }) {
  return (
    <>
      {text.split("\n").map((line, i) => (
        <Fragment key={i}>
          {i > 0 ? <br /> : null}
          {line.split(/(\*\*[^*]+\*\*)/g).map((part, j) =>
            part.startsWith("**") && part.endsWith("**") && part.length > 4 ? (
              <strong key={j}>{part.slice(2, -2)}</strong>
            ) : (
              <Fragment key={j}>{part}</Fragment>
            )
          )}
        </Fragment>
      ))}
    </>
  );
}

/**
 * When Sheldon offers approaches as cards, the cards carry the detail: keep his opening line and
 * his recommendation, and leave out the prose list that repeats each card.
 */
function textBesideOptions(message: ConversationMessage): string {
  const body = message.body ?? "";
  if (message.metadata?.kind !== "arc_proposal") return body;
  const paragraphs = body.split(/\n\s*\n/).map((p) => p.trim()).filter(Boolean);
  const recommendation = paragraphs.find((p) => /^\**my recommendation/i.test(p));
  return [paragraphs[0], recommendation].filter(Boolean).join("\n\n");
}

function SheldonAvatar() {
  return (
    <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-[var(--primary-950)] text-[var(--accent-green)]">
      <Sparkles size={14} aria-hidden />
    </span>
  );
}

/** One chat bubble: yours on the right, Sheldon's on the left. */
function Bubble({ mine, author, time, children }: { mine: boolean; author: string; time: string; children: React.ReactNode }) {
  return (
    <div className={cn("flex items-end gap-2", mine ? "justify-end" : "justify-start")}>
      {mine ? null : <SheldonAvatar />}
      <div
        className={cn(
          "max-w-[78%] rounded-2xl px-4 py-2.5 text-sm shadow-sm",
          mine
            ? "rounded-br-sm bg-[#DCF1C2] text-[var(--text-default)]"
            : "rounded-bl-sm border border-[var(--surface-border)] bg-white text-[var(--text-default)]"
        )}
      >
        {mine ? null : <p className="mb-1 text-xs font-semibold text-[var(--accent-green-dark)]">{author}</p>}
        <div className="break-words leading-relaxed">{children}</div>
        {time ? <p className="mt-1 text-right text-2xs text-[var(--text-muted)]">{time}</p> : null}
      </div>
    </div>
  );
}

/** Seconds since Sheldon started on the current message; resets when he is idle. */
function useElapsedSeconds(running: boolean): number {
  const [seconds, setSeconds] = useState(0);
  useEffect(() => {
    if (!running) return;
    const started = Date.now();
    const tick = () => setSeconds(Math.round((Date.now() - started) / 1000));
    tick();
    const id = window.setInterval(tick, 1000);
    return () => window.clearInterval(id);
  }, [running]);
  return running ? seconds : 0;
}

// What Sheldon is "doing" while he works: a consultant's working vocabulary, shown at random.
const WORKING_WORDS = [
  "Framing the problem",
  "Structuring the storyline",
  "Synthesizing",
  "Pressure-testing assumptions",
  "Sharpening the so-what",
  "Triangulating",
  "Building the business case",
  "Sizing the opportunity",
  "Benchmarking",
  "Mapping the value chain",
  "Finding the 80/20",
  "Sequencing the roadmap",
  "Prioritizing quick wins",
  "Stress-testing the hypothesis",
  "Connecting the dots",
  "Whiteboarding",
  "Aligning stakeholders",
  "Checking the numbers",
  "Drafting the executive summary",
  "Polishing the narrative",
];

/** A working word that changes every few seconds while Sheldon is busy. */
function useWorkingWord(running: boolean): string {
  const [index, setIndex] = useState(0);
  useEffect(() => {
    if (!running) return;
    const next = () => setIndex((prev) => (prev + 1 + Math.floor(Math.random() * (WORKING_WORDS.length - 1))) % WORKING_WORDS.length);
    next();
    const id = window.setInterval(next, 3500);
    return () => window.clearInterval(id);
  }, [running]);
  return WORKING_WORDS[index];
}

function TypingDots() {
  return (
    <span className="inline-flex items-center gap-1" aria-hidden>
      {[0, 150, 300].map((delay) => (
        <span
          key={delay}
          className="h-1.5 w-1.5 animate-bounce rounded-full bg-[var(--text-muted)]"
          style={{ animationDelay: `${delay}ms` }}
        />
      ))}
    </span>
  );
}

export function ConversationThread({
  scopeSummary,
  messages,
  pendingText,
  onCreateDrafts,
  onReply,
  onDraft,
  busy,
}: ReplyHandlers & {
  scopeSummary: string;
  messages: ConversationMessage[];
  // The message you just sent, shown at once while Sheldon is still replying.
  pendingText?: string | null;
  onCreateDrafts?: () => void;
  busy?: boolean;
}) {
  const endRef = useRef<HTMLDivElement | null>(null);
  const elapsed = useElapsedSeconds(Boolean(busy));
  const workingWord = useWorkingWord(Boolean(busy));
  // Your message is shown as sent the moment you press Send.
  const sentAt = useMemo(
    () => (pendingText ? new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : ""),
    [pendingText]
  );
  const lastAnswer = [...messages].reverse().find((m) => m.role === "assistant")?.body ?? "";

  // Keep the newest message in view, as a chat does.
  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages.length, pendingText, busy]);

  return (
    <Card className="flex flex-col gap-3 p-0">
      <div className="flex items-center gap-2 border-b border-[var(--surface-border)] px-4 py-3 text-sm text-[var(--text-muted)]">
        <span className="h-2 w-2 rounded-full bg-[var(--accent-green)]" aria-hidden />
        <span className="font-semibold text-[var(--text-default)]">Sheldon</span>
        <span>· {scopeSummary}</span>
      </div>

      <div
        className="flex max-h-[60vh] min-h-[320px] flex-col gap-3 overflow-y-auto bg-[var(--primary-50)] px-4 py-3"
        aria-live="polite"
      >
        {messages.map((message, i) => {
          const options = message.role === "assistant" && hasReplyOptions(message.metadata) ? message.metadata : null;
          // Only the newest message's choices can still be picked.
          const open = i === messages.length - 1 && !busy;
          return (
            <Bubble key={message.id} mine={message.role === "user"} author={message.author} time={message.timestamp}>
              <FormattedText text={options ? textBesideOptions(message) : (message.body ?? "")} />
              {options ? (
                <ReplyOptions metadata={options} onReply={open ? onReply : undefined} onDraft={open ? onDraft : undefined} />
              ) : null}
            </Bubble>
          );
        })}
        {pendingText ? (
          <Bubble mine author="You" time={sentAt}>
            <FormattedText text={pendingText} />
          </Bubble>
        ) : null}
        {busy ? (
          <Bubble mine={false} author="Sheldon" time="">
            <span className="flex items-center gap-2 text-[var(--text-muted)]">
              <TypingDots />
              {workingWord}…{elapsed >= 3 ? ` ${elapsed}s` : ""}
            </span>
          </Bubble>
        ) : null}
        <div ref={endRef} />
      </div>

      <div className="flex flex-wrap items-center justify-between gap-3 border-t border-[var(--surface-border)] px-4 py-3">
        <Button type="button" className="whitespace-nowrap text-sm" disabled={!onCreateDrafts || busy} onClick={onCreateDrafts}>
          Create PPTX + DOCX drafts
        </Button>
        <Button
          type="button"
          variant="ghost"
          aria-label="Copy Sheldon's latest reply"
          disabled={!lastAnswer}
          onClick={() => void navigator.clipboard.writeText(lastAnswer)}
          className="flex items-center gap-1 px-2 py-1 text-xs"
        >
          <Copy size={16} aria-hidden />
          Copy reply
        </Button>
      </div>
    </Card>
  );
}
