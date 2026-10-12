"use client";

import { ArrowUpRight } from "lucide-react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { ConversationComposer, ConversationThread } from "@/components/conversation";
import { Button } from "@/components/ui/Button";
import { EmptyState } from "@/components/ui/EmptyState";
import { Skeleton } from "@/components/ui/Skeleton";
import { useConversationQuery, useSendMessageMutation } from "@/hooks/useEngagementConversation";
import { useEngagementDetailQuery } from "@/hooks/useEngagements";
import { useAuth } from "@/lib/auth-context";

// Project-scoped conversation page, replacing the flat mock-era
// /conversation route. Reads/sends through the real backend
// (GET/POST /api/projects/{pid}/conversation...) via useEngagementConversation.ts
// — same conversation turn mechanics as the original /projects/[pid] studio
// (frontend/lib/conversationTurn.ts), just rendered with the new UI shell.
export default function EngagementConversationPage() {
  const params = useParams();
  const router = useRouter();
  const { token, ready } = useAuth();
  const [hydrated, setHydrated] = useState(false);

  const id = typeof params.id === "string" ? params.id : Array.isArray(params.id) ? params.id[0] ?? "" : "";
  const engagement = useEngagementDetailQuery(id, Boolean(token));
  const conversation = useConversationQuery(id, Boolean(token));
  const sendMessage = useSendMessageMutation(id);

  useEffect(() => {
    setHydrated(true);
  }, []);

  useEffect(() => {
    if (!ready) return;
    if (!token) router.replace(`/login?next=/engagements/${id}/conversation`);
  }, [ready, token, router, id]);

  if (!hydrated || !ready || !token) {
    return (
      <main style={{ padding: 24 }}>
        <p>Redirecting…</p>
      </main>
    );
  }

  if (conversation.isPending || engagement.isPending) {
    return (
      <main className="space-y-6">
        <Skeleton className="h-4 w-48" />
        <Skeleton className="h-9 w-96" />
        <div className="grid gap-4 lg:grid-cols-[1fr_300px]">
          <Skeleton className="h-96 w-full" />
          <Skeleton className="h-96 w-full" />
        </div>
      </main>
    );
  }

  if (conversation.isError || !conversation.data) {
    return (
      <main className="space-y-4">
        <EmptyState
          title="Conversation unavailable"
          description="This engagement's conversation couldn't be loaded. It may not have one yet."
        >
          <Link href={`/engagements/${id}`}>
            <Button type="button" variant="secondary">
              Back to engagement
            </Button>
          </Link>
        </EmptyState>
      </main>
    );
  }

  const data = conversation.data;
  const engagementName = engagement.data?.name ?? id;
  const scopeSummary =
    data.messages.length > 0
      ? `${data.messages.length} message${data.messages.length === 1 ? "" : "s"} in this conversation`
      : "No messages yet — start the conversation below";

  return (
    <main className="space-y-6">
      <nav className="text-xs uppercase tracking-wide text-[var(--text-muted)]" aria-label="Breadcrumb">
        <Link href={`/engagements/${id}`} className="!text-[var(--text-muted)] !no-underline hover:!text-[var(--text-default)]">
          {engagementName.toUpperCase()}
        </Link>{" "}
        / CONVERSATION
      </nav>

      <header className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-[var(--text-default)]">Conversation</h1>
          <p className="mt-1 text-sm text-[var(--text-muted)]">
            Ask for advice, drafts or revisions — grounded in this engagement&apos;s sources.
          </p>
        </div>
        <Button
          variant="secondary"
          type="button"
          className="flex shrink-0 items-center gap-2"
          onClick={() => router.push(`/engagements/${id}/deliverables`)}
        >
          <ArrowUpRight size={16} aria-hidden />
          View deliverables
        </Button>
      </header>

      <div className="grid gap-4 lg:grid-cols-[1fr_minmax(0,420px)]">
        <div className="space-y-4">
          {data.messages.length ? (
            <ConversationThread scopeSummary={scopeSummary} messages={data.messages} />
          ) : (
            <EmptyState title="No messages yet" description="Send the first message below to start this conversation." />
          )}
          <ConversationComposer
            skillLabel="Advise"
            sourceCount={0}
            busy={sendMessage.isPending}
            onSend={(text) => sendMessage.mutate(text)}
          />
          {sendMessage.isError ? (
            <p className="text-sm text-[#8C5B12]">
              {sendMessage.error instanceof Error ? sendMessage.error.message : "Failed to send message."}
            </p>
          ) : null}
        </div>
      </div>

      <footer className="flex flex-wrap items-center justify-between gap-2 border-t border-[var(--surface-border)] pt-4 text-xs text-[var(--text-muted)]">
        <span>AI-generated advice may be incomplete · Verify citations before sharing</span>
        <span>Advise Workbench · Secure advisory environment</span>
      </footer>
    </main>
  );
}
