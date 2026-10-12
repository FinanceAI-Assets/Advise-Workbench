import { AlertTriangle, Copy, MoreHorizontal, Sparkles, ThumbsDown, ThumbsUp } from "lucide-react";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import type { ConversationMessage } from "@/types/api";

function Citations({ citations }: { citations: number[] }) {
  return (
    <>
      {citations.map((c) => (
        <span key={c} className="ml-1 text-xs font-medium text-[var(--accent-green-dark)]">
          [{c}]
        </span>
      ))}
    </>
  );
}

function UserBubble({ message }: { message: ConversationMessage }) {
  return (
    <div>
      <div className="flex items-baseline justify-between">
        <p className="text-sm font-semibold text-[var(--text-default)]">{message.author}</p>
        <p className="text-xs text-[var(--text-muted)]">{message.timestamp}</p>
      </div>
      <p className="mt-1 text-sm text-[var(--text-default)]">{message.body}</p>
    </div>
  );
}

function AssistantBubble({ message }: { message: ConversationMessage }) {
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="flex h-7 w-7 items-center justify-center rounded-md bg-[var(--primary-950)] text-[var(--accent-green)]">
            <Sparkles size={14} aria-hidden />
          </span>
          <p className="text-sm font-semibold text-[var(--text-default)]">{message.author}</p>
        </div>
        <div className="flex items-center gap-2">
          {message.badge ? (
            <Badge className="border-[var(--surface-border)] bg-[#EFF6E6] text-[#356B12]">{message.badge}</Badge>
          ) : null}
          <span className="text-xs text-[var(--text-muted)]">{message.timestamp}</span>
        </div>
      </div>

      {message.headline ? <p className="text-base font-semibold text-[var(--text-default)]">{message.headline}</p> : null}
      {message.intro ? <p className="text-sm text-[var(--text-muted)]">{message.intro}</p> : null}
      {message.body ? <p className="whitespace-pre-wrap text-sm text-[var(--text-default)]">{message.body}</p> : null}

      {message.phases?.map((phase) => (
        <div key={phase.label}>
          <p className="text-sm font-semibold text-[var(--text-default)]">{phase.label}</p>
          <p className="text-sm text-[var(--text-muted)]">
            {phase.description}
            <Citations citations={phase.citations} />
          </p>
        </div>
      ))}

      {message.evidenceGap ? (
        <div className="flex items-start gap-2 rounded-md border border-[#F3E2C0] bg-[#FCF3E2] p-3">
          <AlertTriangle size={16} className="mt-0.5 shrink-0 text-[#8C5B12]" aria-hidden />
          <div>
            <p className="text-sm font-semibold text-[#8C5B12]">{message.evidenceGap.title}</p>
            <p className="text-xs text-[#8C5B12]">{message.evidenceGap.description}</p>
          </div>
        </div>
      ) : null}
    </div>
  );
}

export function ConversationThread({ scopeSummary, messages }: { scopeSummary: string; messages: ConversationMessage[] }) {
  return (
    <Card className="space-y-6">
      <div className="flex items-center justify-between border-b border-[var(--surface-border)] pb-3">
        <div className="flex items-center gap-2 text-sm text-[var(--text-muted)]">
          <span className="h-2 w-2 rounded-full bg-[var(--accent-green)]" aria-hidden />
          {scopeSummary}
        </div>
        <button type="button" aria-label="Conversation options" className="text-[var(--text-muted)] hover:text-[var(--text-default)]">
          <MoreHorizontal size={18} aria-hidden />
        </button>
      </div>

      {messages.map((message) => (
        <div key={message.id} className="border-b border-[var(--surface-border)] pb-6 last:border-b-0 last:pb-0">
          {message.role === "user" ? <UserBubble message={message} /> : <AssistantBubble message={message} />}
        </div>
      ))}

      <div className="flex flex-wrap items-center justify-between gap-3">
        <Button type="button" className="whitespace-nowrap text-sm">
          Create PPTX + DOCX drafts
        </Button>
        <div className="flex items-center gap-3 text-[var(--text-muted)]">
          <button type="button" aria-label="Copy response" className="hover:text-[var(--text-default)]">
            <Copy size={16} aria-hidden />
          </button>
          <button type="button" aria-label="Good response" className="hover:text-[var(--text-default)]">
            <ThumbsUp size={16} aria-hidden />
          </button>
          <button type="button" aria-label="Bad response" className="hover:text-[var(--text-default)]">
            <ThumbsDown size={16} aria-hidden />
          </button>
        </div>
      </div>
    </Card>
  );
}
