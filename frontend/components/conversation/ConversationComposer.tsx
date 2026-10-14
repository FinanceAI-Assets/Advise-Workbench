"use client";

import { Paperclip } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Textarea } from "@/components/ui/Textarea";

export function ConversationComposer({
  skillLabel,
  sourceCount,
  onSend,
  busy,
  draft,
}: {
  // Text to place in the box; change `draft.id` to apply the same text again.
  draft?: { id: number; text: string };
  skillLabel: string;
  sourceCount: number;
  // Optional: when supplied, Send becomes real — it fires onSend(text) and
  // clears the box. Without it the composer stays purely presentational
  // (mock-era callers keep working unchanged).
  onSend?: (text: string) => void;
  busy?: boolean;
}) {
  const [value, setValue] = useState("");
  const [appliedDraft, setAppliedDraft] = useState(0);
  if (draft && draft.id !== appliedDraft) {
    setAppliedDraft(draft.id);
    setValue(draft.text);
  }

  const submit = () => {
    const text = value.trim();
    if (!text || !onSend || busy) return;
    onSend(text);
    setValue("");
  };

  return (
    <Card className="space-y-3">
      <Textarea
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            submit();
          }
        }}
        placeholder="Message Sheldon…"
        rows={3}
        className="border-0 p-0 focus:ring-0"
      />
      <div className="flex flex-wrap items-center justify-between gap-3 border-t border-[var(--surface-border)] pt-3">
        <div className="flex items-center gap-2 text-sm text-[var(--text-muted)]">
          <Paperclip size={16} aria-hidden />
          <span className="rounded-md bg-[var(--surface-muted)] px-2 py-1 text-xs font-medium text-[var(--text-default)]">
            {skillLabel}
          </span>
          <span>{sourceCount} sources in scope</span>
        </div>
        <Button type="button" className="flex items-center gap-2 text-sm" disabled={!value.trim() || busy} onClick={submit}>
          {busy ? "Sheldon is replying…" : "Send"}
        </Button>
      </div>
      <p className="text-2xs text-[var(--text-muted)]">
        AI-generated advice may be incomplete. Verify citations and obtain human approval before sharing. Shift + Enter for a new line.
      </p>
    </Card>
  );
}
