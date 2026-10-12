"use client";

import { Plus } from "lucide-react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import {
  ArtifactViewer,
  EngagementFilesPanel,
  SlideEvidencePanel,
  VersionHistoryPanel,
  WordArtifactPanel,
} from "@/components/deliverables";
import { EngagementTabs } from "@/components/engagements";
import { Button } from "@/components/ui/Button";
import { EmptyState } from "@/components/ui/EmptyState";
import { Skeleton } from "@/components/ui/Skeleton";
import { useDeliverablesQuery } from "@/hooks/useDeliverables";
import { useAuth } from "@/lib/auth-context";
import { toSlideDetail } from "@/lib/deliverableAdapters";

type DeliverableTabKey = "all" | "powerpoint" | "word" | "evidence-register";

// Project-scoped deliverables page, replacing the flat mock-era
// /deliverables route. Reads the active run's real artifacts
// (pptx_slides.json, narrative_md/sop_markdown, evidence-claims,
// canvas-history) via useDeliverablesQuery(pid).
export default function EngagementDeliverablesPage() {
  const params = useParams();
  const router = useRouter();
  const { token, ready } = useAuth();
  const [hydrated, setHydrated] = useState(false);
  const [tab, setTab] = useState<DeliverableTabKey>("all");
  const [activeFileId, setActiveFileId] = useState<string | null>(null);

  const id = typeof params.id === "string" ? params.id : Array.isArray(params.id) ? params.id[0] ?? "" : "";
  const deliverables = useDeliverablesQuery(id, undefined, Boolean(token));

  useEffect(() => {
    setHydrated(true);
  }, []);

  useEffect(() => {
    if (!ready) return;
    if (!token) router.replace(`/login?next=/engagements/${id}/deliverables`);
  }, [ready, token, router, id]);

  if (!hydrated || !ready || !token) {
    return (
      <main style={{ padding: 24 }}>
        <p>Redirecting…</p>
      </main>
    );
  }

  if (deliverables.isPending) {
    return (
      <main className="space-y-6">
        <Skeleton className="h-4 w-48" />
        <Skeleton className="h-9 w-96" />
        <div className="grid gap-4 lg:grid-cols-[280px_1fr_300px]">
          <Skeleton className="h-96 w-full" />
          <Skeleton className="h-96 w-full" />
          <Skeleton className="h-96 w-full" />
        </div>
      </main>
    );
  }

  if (deliverables.isError) {
    return (
      <main className="space-y-4">
        <EmptyState title="Deliverables unavailable" description="Could not load deliverables for this engagement.">
          <Link href={`/engagements/${id}`}>
            <Button type="button" variant="secondary">
              Back to engagement
            </Button>
          </Link>
        </EmptyState>
      </main>
    );
  }

  const data = deliverables.data;

  if (!data) {
    return (
      <main className="space-y-4">
        <nav className="text-xs uppercase tracking-wide text-[var(--text-muted)]" aria-label="Breadcrumb">
          <Link href={`/engagements/${id}`} className="!text-[var(--text-muted)] !no-underline hover:!text-[var(--text-default)]">
            ENGAGEMENT
          </Link>{" "}
          / DELIVERABLES
        </nav>
        <EmptyState
          title="No runs yet"
          description="This engagement has no runs yet, so there are no deliverables to show. Start a conversation to generate one."
        >
          <Link href={`/engagements/${id}/conversation`}>
            <Button type="button">Open conversation</Button>
          </Link>
        </EmptyState>
      </main>
    );
  }

  const selectedFileId = activeFileId ?? data.files[0]?.id ?? "";
  const selectedFile = data.files.find((f) => f.id === selectedFileId);

  const tabs = [
    { key: "all" as const, label: "All artifacts", count: data.tabCounts.all },
    { key: "powerpoint" as const, label: "PowerPoint", count: data.tabCounts.powerpoint },
    { key: "word" as const, label: "Word", count: data.tabCounts.word },
    { key: "evidence-register" as const, label: "Evidence register", count: data.tabCounts.evidenceRegister },
  ];

  // Resolves any slide index to its full SlideDetail from the raw
  // pptx_slides.json array the hook carries alongside the built
  // DeliverablesDetail, so browsing slides shows real content for every
  // slide, not just the initially-active one.
  const getSlideDetail = (index: number) =>
    toSlideDetail(data.rawSlides[index], index, data.rawSlides.length, data.slideBreadcrumb, data.slideSourcesSummary, data.slideFooterMeta);

  return (
    <main className="space-y-6">
      <nav className="text-xs uppercase tracking-wide text-[var(--text-muted)]" aria-label="Breadcrumb">
        <Link href={`/engagements/${id}`} className="!text-[var(--text-muted)] !no-underline hover:!text-[var(--text-default)]">
          {data.engagementName.toUpperCase()}
        </Link>{" "}
        / DELIVERABLES
      </nav>

      <header className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-[var(--text-default)]">{data.title}</h1>
          <p className="mt-1 text-sm text-[var(--text-muted)]">{data.subtitle}</p>
        </div>
        <Button
          type="button"
          className="flex shrink-0 items-center gap-2"
          onClick={() => router.push(`/engagements/${id}/conversation`)}
        >
          <Plus size={16} aria-hidden />
          Create deliverable
        </Button>
      </header>

      <EngagementTabs tabs={tabs} active={tab} onChange={setTab} />

      {tab !== "all" ? (
        <EmptyState
          title={`${tabs.find((t) => t.key === tab)?.label} view is coming soon`}
          description={`This filtered view isn't wired up yet in this preview — browse artifacts from "All artifacts".`}
        />
      ) : (
        <div className="grid gap-4 lg:grid-cols-[280px_1fr_300px]">
          <div className="space-y-4">
            <EngagementFilesPanel files={data.files} activeFileId={selectedFileId} onSelect={setActiveFileId} />
            <VersionHistoryPanel versions={data.versions} />
          </div>

          <div className="space-y-4">
            {selectedFile?.type === "pptx" ? (
              <>
                <ArtifactViewer pptx={data.pptx} getSlideDetail={getSlideDetail} />
                <SlideEvidencePanel links={data.pptx.evidenceLinks} />
              </>
            ) : (
              <EmptyState
                title={`${selectedFile?.name ?? "This artifact"} preview is coming soon`}
                description="This preview isn't wired up yet — select the deliverable deck to see the full artifact viewer."
              />
            )}
          </div>

          <div className="space-y-4">
            <WordArtifactPanel docx={data.docx} />
          </div>
        </div>
      )}
    </main>
  );
}
