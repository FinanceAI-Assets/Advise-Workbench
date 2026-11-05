"use client";

import { BookOpen, MessagesSquare } from "lucide-react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import {
  DeliverablesStrip,
  EngagementBriefCard,
  EngagementTabs,
  type EngagementTabKey,
  EvidenceReadinessPanel,
  MilestonesTable,
  TeamAccessPanel,
} from "@/components/engagements";
import {
  ActivitySection,
  BriefSection,
  DraftSection,
  ExportSection,
  ReviewSection,
  SourcesSection,
  TeamSection,
} from "@/components/engagements/EngagementSections";
import { Button } from "@/components/ui/Button";
import { EmptyState } from "@/components/ui/EmptyState";
import { Skeleton } from "@/components/ui/Skeleton";
import { useEngagementDetailQuery } from "@/hooks/useEngagements";
import { useAuth } from "@/lib/auth-context";

// Workflow views without a tab of their own; each highlights the tab it belongs to.
type StepView = "brief" | "draft" | "review" | "export";

const STEP_TAB: Record<StepView, EngagementTabKey> = {
  brief: "overview",
  draft: "overview",
  review: "overview",
  export: "overview",
};

export default function EngagementDetailPage() {
  const params = useParams();
  const router = useRouter();
  const { token, ready } = useAuth();
  const [hydrated, setHydrated] = useState(false);
  const [tab, setTab] = useState<EngagementTabKey | StepView>("overview");

  const id = typeof params.id === "string" ? params.id : Array.isArray(params.id) ? params.id[0] ?? "" : "";
  const detail = useEngagementDetailQuery(id, Boolean(token));

  useEffect(() => {
    setHydrated(true);
    // Deep links such as ?tab=sources open that view.
    const requested = new URLSearchParams(window.location.search).get("tab");
    if (requested && ["sources", "team", "activity", "brief", "draft", "review", "export"].includes(requested)) {
      setTab(requested as EngagementTabKey | StepView);
    }
  }, []);

  useEffect(() => {
    if (!ready) return;
    if (!token) router.replace(`/login?next=/engagements/${id}`);
  }, [ready, token, router, id]);

  if (!hydrated || !ready || !token) {
    return (
      <main style={{ padding: 24 }}>
        <p>Redirecting…</p>
      </main>
    );
  }

  if (detail.isPending) {
    return (
      <main className="space-y-6">
        <Skeleton className="h-4 w-40" />
        <Skeleton className="h-9 w-80" />
        <Skeleton className="h-24 w-full" />
        <Skeleton className="h-64 w-full" />
      </main>
    );
  }

  if (detail.isError || !detail.data) {
    return (
      <main className="space-y-4">
        <EmptyState
          title="Engagement not found"
          description="This engagement may have been removed or you don't have access to it."
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

  const data = detail.data;

  const tabs = [
    { key: "overview" as const, label: "Overview" },
    { key: "sources" as const, label: "Sources" },
    { key: "team" as const, label: "Access" },
    { key: "activity" as const, label: "Activity" },
  ];

  return (
    <main className="space-y-6">
      <nav className="text-xs tracking-wide text-[var(--text-muted)]" aria-label="Breadcrumb">
        <Link href="/engagements" className="!text-[var(--text-muted)] !no-underline hover:!text-[var(--text-default)]">
          ENGAGEMENTS
        </Link>{" "}
        / {data.code}
      </nav>

      <header className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-[var(--text-default)]">{data.name}</h1>
          <p className="mt-1 text-sm text-[var(--text-muted)]">
            {data.subtitle} · {data.dateRange} · Engagement lead: {data.lead}
          </p>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <Link href="/library" className="!no-underline">
            <Button type="button" variant="secondary" className="flex items-center gap-2">
              <BookOpen size={16} aria-hidden />
              Browse the library
            </Button>
          </Link>
          <Button type="button" className="flex items-center gap-2" onClick={() => router.push(`/engagements/${id}/conversation`)}>
            <MessagesSquare size={16} aria-hidden />
            Open conversation
          </Button>
        </div>
      </header>

      <div className="grid gap-4 lg:grid-cols-[2fr_1fr]">
        <EngagementTabs
          large
          tabs={tabs}
          active={tab in STEP_TAB ? STEP_TAB[tab as StepView] : (tab as EngagementTabKey)}
          onChange={setTab}
        />
      </div>

      {tab === "overview" ? (
        <section className="grid gap-4 lg:grid-cols-[2fr_1fr]">
          <div className="space-y-4">
            <EngagementBriefCard brief={data.brief} onEdit={() => setTab("brief")} />
            <MilestonesTable milestones={data.milestones} />
          </div>
          <div className="space-y-4">
            <TeamAccessPanel members={data.teamMembers} memberCount={data.teamMemberCount} note={data.teamNote} />
            <EvidenceReadinessPanel
              sourceCount={data.evidenceSourceCount}
              sources={data.evidenceSources}
              warning={data.evidenceWarning}
              onViewAll={() => setTab("sources")}
            />
          </div>
        </section>
      ) : null}
      {tab === "sources" ? <SourcesSection id={id} detail={data} /> : null}
      {tab === "team" ? <TeamSection id={id} detail={data} /> : null}
      {tab === "activity" ? <ActivitySection id={id} /> : null}
      {tab === "brief" ? <BriefSection id={id} detail={data} onContinue={() => setTab("sources")} /> : null}
      {tab === "draft" ? <DraftSection id={id} detail={data} /> : null}
      {tab === "review" ? <ReviewSection detail={data} /> : null}
      {tab === "export" ? <ExportSection id={id} /> : null}

      {tab === "overview" ? <DeliverablesStrip deliverables={data.deliverables} /> : null}
    </main>
  );
}
