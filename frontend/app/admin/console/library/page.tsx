"use client";

import { Upload } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { IngestionJobPanel, PracticeInventoryTable, QualityReviewPanel } from "@/components/admin-console";
import { EngagementStepper } from "@/components/engagements";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Select } from "@/components/ui/Select";
import { Skeleton } from "@/components/ui/Skeleton";
import { useAdminLibraryQuery } from "@/hooks/useAdminLibrary";
import { useAuth } from "@/lib/auth-context";

export default function AdminConsoleLibraryPage() {
  const router = useRouter();
  const { token, ready } = useAuth();
  const [hydrated, setHydrated] = useState(false);
  const [activeId, setActiveId] = useState<string | null>(null);

  const library = useAdminLibraryQuery(Boolean(token));

  useEffect(() => {
    setHydrated(true);
  }, []);

  useEffect(() => {
    if (!ready) return;
    if (!token) router.replace("/login?next=/admin/console/library");
  }, [ready, token, router]);

  if (!hydrated || !ready || !token) {
    return (
      <main style={{ padding: 24 }}>
        <p>Redirecting…</p>
      </main>
    );
  }

  if (library.isPending || !library.data) {
    return (
      <main className="space-y-6">
        <Skeleton className="h-4 w-48" />
        <Skeleton className="h-9 w-96" />
        <Skeleton className="h-64 w-full" />
      </main>
    );
  }

  const data = library.data;
  const activePracticeId = activeId ?? data.qualityReview.id;
  const showingSelected = activePracticeId === data.qualityReview.id;

  return (
    <main className="space-y-6">
      <nav className="text-xs uppercase tracking-wide text-[var(--text-muted)]" aria-label="Breadcrumb">
        Admin console / Leading Practice Library
      </nav>

      <header className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-[var(--text-default)]">Library management</h1>
          <p className="mt-1 text-sm text-[var(--text-muted)]">
            Ingest, verify and publish versioned practices. Only approved releases are available for user retrieval.
          </p>
        </div>
        <Button type="button" className="flex shrink-0 items-center gap-2 whitespace-nowrap">
          <Upload size={16} aria-hidden />
          Upload sources
        </Button>
      </header>

      <EngagementStepper steps={data.pipelineSteps} />

      <div className="grid gap-4 lg:grid-cols-[1fr_380px]">
        <div className="space-y-4">
          <div className="flex flex-wrap items-center gap-3">
            <Input placeholder="Search practice title, owner or version" className="min-w-[260px] flex-1" />
            <Select defaultValue="all" className="w-auto">
              <option value="all">Lifecycle: All</option>
              <option value="published">Lifecycle: Published</option>
              <option value="review">Lifecycle: Quality review</option>
            </Select>
            <span className="ml-auto text-xs text-[var(--text-muted)]">{data.practiceInventoryTotal}</span>
          </div>
          <PracticeInventoryTable rows={data.practiceInventory} activeId={activePracticeId} onSelect={setActiveId} />
          <IngestionJobPanel job={data.latestIngestionJob} />
        </div>

        {showingSelected ? (
          <QualityReviewPanel review={data.qualityReview} />
        ) : (
          <div className="rounded-lg border border-[var(--surface-border)] bg-white p-6 text-sm text-[var(--text-muted)]">
            This practice&apos;s review detail isn&apos;t wired up yet in this demo.
          </div>
        )}
      </div>

      <footer className="flex flex-wrap items-center justify-between gap-2 border-t border-[var(--surface-border)] pt-4 text-xs text-[var(--text-muted)]">
        <span>Illustrative content only · No real client or confidential information</span>
        <span>Advise Workbench · Secure advisory environment</span>
      </footer>
    </main>
  );
}
