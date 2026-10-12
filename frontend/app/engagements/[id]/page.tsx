"use client";

import { FileText, Share2, UserPlus } from "lucide-react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import {
  DeliverablesStrip,
  EngagementBriefCard,
  EngagementStepper,
  EngagementTabs,
  type EngagementTabKey,
  EvidenceReadinessPanel,
  MilestonesTable,
  TeamAccessPanel,
} from "@/components/engagements";
import { Button } from "@/components/ui/Button";
import { EmptyState } from "@/components/ui/EmptyState";
import { Skeleton } from "@/components/ui/Skeleton";
import { useEngagementDetailQuery } from "@/hooks/useEngagements";
import { useAuth } from "@/lib/auth-context";

export default function EngagementDetailPage() {
  const params = useParams();
  const router = useRouter();
  const { token, ready } = useAuth();
  const [hydrated, setHydrated] = useState(false);
  const [tab, setTab] = useState<EngagementTabKey>("overview");

  const id = typeof params.id === "string" ? params.id : Array.isArray(params.id) ? params.id[0] ?? "" : "";
  const detail = useEngagementDetailQuery(id, Boolean(token));

  useEffect(() => {
    setHydrated(true);
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
    { key: "sources" as const, label: "Sources", count: data.tabCounts.sources },
    { key: "deliverables" as const, label: "Deliverables", count: data.tabCounts.deliverables },
    { key: "team" as const, label: "Team", count: data.tabCounts.team },
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
          <Button variant="secondary" type="button" className="flex items-center gap-2">
            <UserPlus size={16} aria-hidden />
            Manage access
          </Button>
          <Button
            variant="secondary"
            type="button"
            className="flex items-center gap-2"
            onClick={() => router.push(`/engagements/${id}/deliverables`)}
          >
            <FileText size={16} aria-hidden />
            View deliverables
          </Button>
          <Button type="button" className="flex items-center gap-2" onClick={() => router.push(`/engagements/${id}/conversation`)}>
            <Share2 size={16} aria-hidden />
            Open conversation
          </Button>
        </div>
      </header>

      <EngagementStepper steps={data.steps} />

      <EngagementTabs tabs={tabs} active={tab} onChange={setTab} />

      {tab === "overview" ? (
        <section className="grid gap-4 lg:grid-cols-[2fr_1fr]">
          <div className="space-y-4">
            <EngagementBriefCard brief={data.brief} />
            <MilestonesTable milestones={data.milestones} />
          </div>
          <div className="space-y-4">
            <TeamAccessPanel members={data.teamMembers} memberCount={data.teamMemberCount} note={data.teamNote} />
            <EvidenceReadinessPanel
              sourceCount={data.evidenceSourceCount}
              sources={data.evidenceSources}
              warning={data.evidenceWarning}
            />
          </div>
        </section>
      ) : (
        <EmptyState
          title={`${tabs.find((t) => t.key === tab)?.label} is coming soon`}
          description="This tab isn't wired up yet in this preview."
        />
      )}

      {tab === "overview" ? <DeliverablesStrip deliverables={data.deliverables} /> : null}
    </main>
  );
}
