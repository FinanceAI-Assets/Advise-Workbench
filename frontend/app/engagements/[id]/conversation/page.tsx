"use client";

import { ArrowUpRight, Plus } from "lucide-react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import {
  ActiveSkillPanel,
  ConversationComposer,
  ConversationThread,
  ConversationUsageCard,
  EngagementContextPanel,
  PermissionAwareCard,
  RecentConversationsList,
} from "@/components/conversation";
import { RunProgressCard } from "@/components/conversation/RunProgressCard";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { Input } from "@/components/ui/Input";
import { ErrorNote, PageFrame, PageSkeleton } from "@/components/workbench/PageFrame";
import { useConversationQuery, useSendMessageMutation } from "@/hooks/useEngagementConversation";
import { useEngagementDetailQuery } from "@/hooks/useEngagements";
import {
  handoffDraftKey,
  useActivateConversationMutation,
  useConversationContextQuery,
  useSelectSkillMutation,
  useStartConversationMutation,
} from "@/hooks/useWorkbench";

const DRAFT_REQUEST = "Create PPTX and DOCX drafts from this conversation, grounded in the permitted sources.";
// Conversation for one engagement. Messages go through the existing
// conversation pipeline (POST /api/projects/{pid}/conversation/messages); the
// active thread, skill and source scope come from /api/engagements/{pid}/conversations.
export default function EngagementConversationPage() {
  const params = useParams();
  const router = useRouter();
  const id = typeof params.id === "string" ? params.id : Array.isArray(params.id) ? (params.id[0] ?? "") : "";

  const engagement = useEngagementDetailQuery(id);
  const conversation = useConversationQuery(id);
  const context = useConversationContextQuery(id);
  const sendMessage = useSendMessageMutation(id);
  const startConversation = useStartConversationMutation(id);
  const activate = useActivateConversationMutation(id);
  const selectSkill = useSelectSkillMutation();
  const [newTitle, setNewTitle] = useState<string | null>(null);
  const [draft, setDraft] = useState({ id: 0, text: "" });

  // A brief handed off from the library's "Use in engagement" waits in the composer for review; it is not sent.
  useEffect(() => {
    if (!id) return;
    const brief = window.sessionStorage.getItem(handoffDraftKey(id));
    if (!brief) return;
    window.sessionStorage.removeItem(handoffDraftKey(id));
    setDraft((prev) => ({ id: prev.id + 1, text: brief }));
  }, [id]);

  if (conversation.isPending || engagement.isPending || context.isPending) return <PageSkeleton />;

  if (conversation.isError || !conversation.data || !engagement.data) {
    return (
      <main className="space-y-4">
        <EmptyState
          title="Conversation unavailable"
          description="This engagement's conversation couldn't be loaded, or you don't have access to it."
        >
          <Link href="/engagements">
            <Button type="button" variant="secondary">
              Back to engagements
            </Button>
          </Link>
        </EmptyState>
      </main>
    );
  }

  const data = conversation.data;
  const engagementData = engagement.data;
  const ctx = context.data;
  const active = ctx?.items.find((item) => item.active);
  const skill = ctx?.skill ?? null;
  const sources = ctx?.sources ?? { documents: [], practices: [], total: 0 };
  const scopeSummary = `Scope: ${sources.documents.length} engagement document${
    sources.documents.length === 1 ? "" : "s"
  } · ${sources.practices.length} approved library practice${sources.practices.length === 1 ? "" : "s"}`;

  async function createConversation(e: React.FormEvent) {
    e.preventDefault();
    if (!newTitle?.trim()) return;
    await startConversation.mutateAsync(newTitle.trim());
    setNewTitle(null);
  }

  return (
    <PageFrame
      breadcrumb={
        <>
          <Link href={`/engagements/${id}`}>{engagementData.name}</Link> / Conversation
        </>
      }
      title={active?.label ?? "From evidence to advice"}
      subtitle={`${engagementData.name} · ${engagementData.code} · Ask for advice, drafts or revisions grounded in this engagement's sources.`}
      actions={
        <>
          <Button variant="secondary" type="button" className="flex items-center gap-2" onClick={() => setNewTitle("")}>
            <Plus size={16} aria-hidden />
            New conversation
          </Button>
          <Button
            variant="secondary"
            type="button"
            className="flex items-center gap-2"
            onClick={() => router.push(`/engagements/${id}/deliverables`)}
          >
            <ArrowUpRight size={16} aria-hidden />
            View artifacts
          </Button>
        </>
      }
    >
      {newTitle !== null ? (
        <Card>
          <form onSubmit={(e) => void createConversation(e)} className="flex flex-wrap items-end gap-3">
            <label className="grid flex-1 gap-1.5 text-2xs font-semibold uppercase tracking-wide text-[var(--text-muted)]">
              Conversation title
              <Input
                autoFocus
                required
                minLength={3}
                value={newTitle}
                onChange={(e) => setNewTitle(e.target.value)}
                placeholder="For example: Service ownership options"
              />
            </label>
            <Button type="submit" disabled={startConversation.isPending}>
              Start conversation
            </Button>
            <Button type="button" variant="secondary" onClick={() => setNewTitle(null)}>
              Cancel
            </Button>
            <p className="w-full text-xs text-[var(--text-muted)]">
              Starts a new evidence-led thread without changing existing conversations.
            </p>
            <ErrorNote error={startConversation.error} />
          </form>
        </Card>
      ) : null}

      <RunProgressCard pid={id} />

      <div className="grid gap-4 lg:grid-cols-[280px_1fr_340px]">
        <div className="space-y-4">
          <EngagementContextPanel
            context={{
              classification: engagementData.brief.classification,
              name: engagementData.name,
              description: engagementData.brief.summary,
              lead: engagementData.lead,
              teamNote: engagementData.teamNote,
            }}
          />
          {skill ? (
            <ActiveSkillPanel
              skill={skill}
              options={ctx?.skills}
              selectedId={skill.id}
              onChange={(skillId) => selectSkill.mutate({ skillId, projectId: id })}
            />
          ) : null}
          {ctx && ctx.items.length > 0 ? (
            <Card>
              <RecentConversationsList items={ctx.items} onSelect={(cid) => activate.mutate(cid)} />
            </Card>
          ) : null}
        </div>

        <div className="space-y-4">
          <ConversationThread
            scopeSummary={scopeSummary}
            messages={data.messages}
            pendingText={sendMessage.isPending ? sendMessage.variables : null}
            busy={sendMessage.isPending}
            onCreateDrafts={() => sendMessage.mutate(DRAFT_REQUEST)}
            onReply={(text) => sendMessage.mutate(text)}
            onDraft={(text) => setDraft((prev) => ({ id: prev.id + 1, text }))}
          />
          <ConversationComposer
            skillLabel={skill?.name ?? "Conversation"}
            sourceCount={sources.total}
            busy={sendMessage.isPending}
            draft={draft}
            onSend={(text) => sendMessage.mutate(text)}
          />
          <ErrorNote error={sendMessage.error} />
        </div>

        <div className="space-y-4">
          <Card className="space-y-3">
            <div className="flex items-center justify-between">
              <h2 className="text-base font-semibold text-[var(--text-default)]">Sources in scope</h2>
              <span className="text-xs text-[var(--text-muted)]">{sources.total}</span>
            </div>
            {sources.total === 0 ? (
              <p className="text-xs text-[var(--text-muted)]">No sources yet. Add documents or approved practices.</p>
            ) : (
              <ul className="space-y-2">
                {sources.practices.map((practice) => (
                  <li key={practice.id} className="border-b border-[var(--surface-border)] pb-2 last:border-b-0">
                    <Link href={`/library?practice=${practice.id}`} className="text-sm font-medium">
                      {practice.title}
                    </Link>
                    <p className="text-xs text-[var(--text-muted)]">Approved library practice</p>
                  </li>
                ))}
                {sources.documents.map((name) => (
                  <li key={name} className="border-b border-[var(--surface-border)] pb-2 last:border-b-0 last:pb-0">
                    <p className="truncate text-sm font-medium text-[var(--text-default)]">{name}</p>
                    <p className="text-xs text-[var(--text-muted)]">Engagement document · Internal</p>
                  </li>
                ))}
              </ul>
            )}
            <Link href={`/engagements/${id}?tab=sources`} className="block !no-underline">
              <Button variant="secondary" className="w-full justify-center">
                Manage sources
              </Button>
            </Link>
          </Card>
          <PermissionAwareCard />
          <ConversationUsageCard pid={id} busy={sendMessage.isPending} />
        </div>
      </div>
    </PageFrame>
  );
}
