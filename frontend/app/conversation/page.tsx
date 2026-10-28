"use client";

import { Plus } from "lucide-react";
import { useRouter } from "next/navigation";
import { type FormEvent, useState } from "react";

import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Input } from "@/components/ui/Input";
import { Select } from "@/components/ui/Select";
import { EngagementPicker } from "@/components/workbench/EngagementPicker";
import { ErrorNote } from "@/components/workbench/PageFrame";
import { useEngagementsQuery } from "@/hooks/useEngagements";
import { useStartConversationInMutation } from "@/hooks/useWorkbench";

/** Start a new thread in a chosen engagement, then open that engagement's conversation. */
function NewConversationForm({ onCancel }: { onCancel: () => void }) {
  const router = useRouter();
  const engagements = useEngagementsQuery({ q: "", status: "active", mine: false, page: 1 });
  const start = useStartConversationInMutation();
  const rows = engagements.data?.items ?? [];
  const [projectId, setProjectId] = useState("");
  const [title, setTitle] = useState("");
  const target = projectId || rows[0]?.id || "";

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!target || !title.trim()) return;
    await start.mutateAsync({ pid: target, title: title.trim() });
    router.push(`/engagements/${target}/conversation`);
  }

  return (
    <Card>
      <form onSubmit={(e) => void submit(e)} className="flex flex-wrap items-end gap-3">
        <label className="grid min-w-[220px] flex-1 gap-1.5 text-2xs font-semibold uppercase tracking-wide text-[var(--text-muted)]">
          Engagement
          <Select value={target} onChange={(e) => setProjectId(e.target.value)} required>
            {rows.map((row) => (
              <option key={row.id} value={row.id}>
                {row.name} · {row.code}
              </option>
            ))}
          </Select>
        </label>
        <label className="grid min-w-[260px] flex-[2] gap-1.5 text-2xs font-semibold uppercase tracking-wide text-[var(--text-muted)]">
          Conversation title
          <Input
            autoFocus
            required
            minLength={3}
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="For example: Service ownership options"
          />
        </label>
        <Button type="submit" disabled={!target || start.isPending}>
          {start.isPending ? "Starting…" : "Start conversation"}
        </Button>
        <Button type="button" variant="secondary" onClick={onCancel}>
          Cancel
        </Button>
        <p className="w-full text-xs text-[var(--text-muted)]">
          Starts a new evidence-led thread in that engagement without changing its existing conversations.
        </p>
        <ErrorNote error={start.error} />
      </form>
    </Card>
  );
}

export default function ConversationIndexPage() {
  const [creating, setCreating] = useState(false);
  return (
    <EngagementPicker
      area="conversation"
      title="Conversation"
      subtitle="Choose an engagement to continue its conversation. Every thread stays inside its engagement's sources."
      actions={
        <Button variant="secondary" type="button" className="flex items-center gap-2" onClick={() => setCreating(true)}>
          <Plus size={16} aria-hidden />
          New conversation
        </Button>
      }
    >
      {creating ? <NewConversationForm onCancel={() => setCreating(false)} /> : null}
    </EngagementPicker>
  );
}
