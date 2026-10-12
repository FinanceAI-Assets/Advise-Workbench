"use client";

import { ArrowUpRight, Plus } from "lucide-react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import {
  ActiveSkillPanel,
  ConversationComposer,
  ConversationThread,
  EngagementContextPanel,
  PermissionAwareCard,
  PracticeContextPanel,
} from "@/components/conversation";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { Skeleton } from "@/components/ui/Skeleton";
import { useConversationQuery, useSendMessageMutation } from "@/hooks/useEngagementConversation";
import { useEngagementDetailQuery } from "@/hooks/useEngagements";
import { useAuth } from "@/lib/auth-context";
import type { ActiveSkill, PracticeContext } from "@/types/api";

// Active skill and practice context have no backend equivalent yet (no
// per-conversation skill-selection or practice-match endpoint) — kept as a
// fixed default rather than fabricated-but-dynamic content, following the
// same real-data-first / clearly-scoped-default split as useLpLibrary.ts and
// useReview.ts. Everything else on this page (engagement context, messages,
// evidence-shown count) is real.
const DEFAULT_SKILL: ActiveSkill = {
  name: "Roadmap builder",
  version: "v2.1",
  meta: "Evidence required · Human review before export",
  formats: ["PPTX + DOCX"],
};

const DEFAULT_PRACTICE: PracticeContext = {
  name: "Operating model design",
  meta: "Playbook v3.2 · Managed maturity · Approved 06 Oct 2026",
  practiceHref: "/admin/lp-library",
};

// Project-scoped conversation page, replacing the flat mock-era
// /conversation route. Reads/sends through the real backend
// (GET/POST /api/projects/{pid}/conversation...) via useEngagementConversation.ts
// — same conversation turn mechanics as the original /projects/[pid] studio
// (frontend/lib/conversationTurn.ts), rendered in the engagement-context +
// conversation + evidence three-column layout.
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
        <div className="grid gap-4 lg:grid-cols-[280px_1fr_340px]">
          <Skeleton className="h-96 w-full" />
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
  const engagementData = engagement.data;
  const engagementName = engagementData?.name ?? id;
  const scopeSummary = engagementData
    ? `Scope: ${engagementData.teamMemberCount} engagement${engagementData.teamMemberCount === 1 ? "" : "s"} · ${engagementData.evidenceSourceCount} approved library sources`
    : "No scope information available";

  // Uploaded documents are real, but the backend has no per-conversation
  // relevance-ranked retrieval endpoint yet — fabricating a relevance score
  // or quote for a real filename would misrepresent it, so only indexed
  // source names/counts are shown, not EvidenceMatch's full ranked shape.
  const evidenceSources = engagementData?.evidenceSources ?? [];

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
          <h1 className="text-2xl font-semibold text-[var(--text-default)]">From evidence to advice</h1>
          <p className="mt-1 text-sm text-[var(--text-muted)]">
            Roadmap planning · Ask for advice, drafts or revisions — grounded in this engagement&apos;s sources.
          </p>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <Button
            variant="secondary"
            type="button"
            className="flex items-center gap-2"
            onClick={() => router.push(`/engagements/${id}/conversation`)}
          >
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
        </div>
      </header>

      <div className="grid gap-4 lg:grid-cols-[280px_1fr_340px]">
        <div className="space-y-4">
          {engagementData ? (
            <EngagementContextPanel
              context={{
                classification: engagementData.brief.classification,
                name: engagementData.name,
                description: engagementData.brief.summary,
                lead: engagementData.lead,
                teamNote: `${engagementData.teamMemberCount} team member${engagementData.teamMemberCount === 1 ? "" : "s"} · Scoped access`,
              }}
            />
          ) : null}
          <ActiveSkillPanel skill={DEFAULT_SKILL} />
          <PracticeContextPanel practice={DEFAULT_PRACTICE} />
        </div>

        <div className="space-y-4">
          {data.messages.length ? (
            <ConversationThread scopeSummary={scopeSummary} messages={data.messages} />
          ) : (
            <EmptyState title="No messages yet" description="Send the first message below to start this conversation." />
          )}
          <ConversationComposer
            skillLabel={DEFAULT_SKILL.name}
            sourceCount={engagementData?.evidenceSourceCount ?? 0}
            busy={sendMessage.isPending}
            onSend={(text) => sendMessage.mutate(text)}
          />
          {sendMessage.isError ? (
            <p className="text-sm text-[#8C5B12]">
              {sendMessage.error instanceof Error ? sendMessage.error.message : "Failed to send message."}
            </p>
          ) : null}
        </div>

        <div className="space-y-4">
          <Card className="space-y-3">
            <div className="flex items-center justify-between">
              <h2 className="text-base font-semibold text-[var(--text-default)]">Indexed sources</h2>
              <span className="text-xs text-[var(--text-muted)]">{evidenceSources.length}</span>
            </div>
            {evidenceSources.length ? (
              <ul className="space-y-2">
                {evidenceSources.map((source) => (
                  <li key={source.id} className="border-b border-[var(--surface-border)] pb-2 last:border-b-0 last:pb-0">
                    <p className="truncate text-sm font-medium text-[var(--text-default)]">{source.label}</p>
                    <p className="text-xs text-[var(--text-muted)]">{source.value}</p>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-xs text-[var(--text-muted)]">No documents uploaded to this engagement yet.</p>
            )}
          </Card>
          <PermissionAwareCard />
        </div>
      </div>

      <footer className="flex flex-wrap items-center justify-between gap-2 border-t border-[var(--surface-border)] pt-4 text-xs text-[var(--text-muted)]">
        <span>Illustrative content only · No real client or confidential information</span>
        <span>Advise Workbench · Secure advisory environment</span>
      </footer>
    </main>
  );
}
