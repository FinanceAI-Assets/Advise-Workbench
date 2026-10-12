"use client";

import { Save, Send } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { EngagementStepper } from "@/components/engagements";
import { ApprovalPanel, DraftPreviewPanel, EvidenceChecksTable, ReviewCommentsPanel } from "@/components/reviews";
import { Button } from "@/components/ui/Button";
import { Skeleton } from "@/components/ui/Skeleton";
import { useReviewQuery } from "@/hooks/useReview";
import { useAuth } from "@/lib/auth-context";

export default function ReviewsPage() {
  const router = useRouter();
  const { token, ready } = useAuth();
  const [hydrated, setHydrated] = useState(false);

  const review = useReviewQuery(Boolean(token));

  useEffect(() => {
    setHydrated(true);
  }, []);

  useEffect(() => {
    if (!ready) return;
    if (!token) router.replace("/login?next=/reviews");
  }, [ready, token, router]);

  if (!hydrated || !ready || !token) {
    return (
      <main style={{ padding: 24 }}>
        <p>Redirecting…</p>
      </main>
    );
  }

  if (review.isPending || !review.data) {
    return (
      <main className="space-y-6">
        <Skeleton className="h-4 w-48" />
        <Skeleton className="h-9 w-96" />
        <Skeleton className="h-20 w-full" />
        <div className="grid gap-4 lg:grid-cols-[1fr_380px]">
          <Skeleton className="h-96 w-full" />
          <Skeleton className="h-96 w-full" />
        </div>
      </main>
    );
  }

  const data = review.data;

  return (
    <main className="space-y-6">
      <nav className="text-xs uppercase tracking-wide text-[var(--text-muted)]" aria-label="Breadcrumb">
        {data.engagementName} / Reviews / {data.code}
      </nav>

      <header className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-[var(--text-default)]">Review: {data.artifactName}</h1>
          <p className="mt-1 text-sm text-[var(--text-muted)]">
            {data.versionLabel} · Owner: {data.owner} · Reviewer: {data.reviewer} · Due {data.dueDate}
          </p>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <Button variant="secondary" type="button" className="flex items-center gap-2 whitespace-nowrap">
            <Save size={16} aria-hidden />
            Save revision
          </Button>
          <Button variant="secondary" type="button" className="flex items-center gap-2 whitespace-nowrap">
            <Send size={16} aria-hidden />
            Submit revised draft
          </Button>
        </div>
      </header>

      <EngagementStepper steps={data.steps} />

      <div className="grid gap-4 lg:grid-cols-[1fr_380px]">
        <div className="space-y-4">
          <DraftPreviewPanel slide={data.slide} versionLabel={data.versionLabel} commentCount={data.slideCommentCount} />
          <EvidenceChecksTable checks={data.evidenceChecks} runMeta={data.evidenceChecksRunMeta} />
        </div>

        <div className="space-y-4">
          <ReviewCommentsPanel comments={data.comments} openCount={data.openCount} resolvedCount={data.resolvedCount} />
          <ApprovalPanel
            approverName={data.approverName}
            approverRole={data.approverRole}
            status={data.approvalStatus}
            timeline={data.approvalTimeline}
          />
        </div>
      </div>
    </main>
  );
}
