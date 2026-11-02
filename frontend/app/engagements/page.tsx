"use client";

import { Plus, Search, SlidersHorizontal, ChevronLeft, ChevronRight } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import {
  EngagementStatCard,
  EngagementsTable,
  NextActionsPanel,
  RecentActivityPanel,
} from "@/components/engagements";
import { Button } from "@/components/ui/Button";
import { EmptyState } from "@/components/ui/EmptyState";
import { Input } from "@/components/ui/Input";
import { Select } from "@/components/ui/Select";
import { Skeleton } from "@/components/ui/Skeleton";
import {
  ENGAGEMENTS_PAGE_SIZE,
  type EngagementListFilters,
  useEngagementStatsQuery,
  useEngagementsQuery,
  useNextActionsQuery,
  useRecentActivityQuery,
} from "@/hooks/useEngagements";
import { useAuth } from "@/lib/auth-context";

export default function EngagementsPage() {
  const router = useRouter();
  const { token, ready } = useAuth();
  const [hydrated, setHydrated] = useState(false);
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState<EngagementListFilters["status"]>("active");
  const [mine, setMine] = useState(false);
  const [page, setPage] = useState(1);

  const engagements = useEngagementsQuery({ q: query, status, mine, page }, Boolean(token));
  const stats = useEngagementStatsQuery(Boolean(token));
  const nextActions = useNextActionsQuery(Boolean(token));
  const recentActivity = useRecentActivityQuery(Boolean(token));

  useEffect(() => {
    setHydrated(true);
  }, []);

  useEffect(() => {
    if (!ready) return;
    if (!token) router.replace("/login?next=/engagements");
  }, [ready, token, router]);

  const rows = engagements.data?.items ?? [];
  const total = engagements.data?.total ?? 0;
  const pageCount = Math.max(1, Math.ceil(total / ENGAGEMENTS_PAGE_SIZE));
  const newEngagement = () => router.push("/engagements/new");

  if (!hydrated || !ready || !token) {
    return (
      <main style={{ padding: 24 }}>
        <p>Redirecting…</p>
      </main>
    );
  }

  return (
    <main className="space-y-6">
      <nav className="text-xs tracking-wide text-[var(--text-muted)]" aria-label="Breadcrumb">
        USER WORKSPACE / ENGAGEMENTS
      </nav>

      <header className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-[var(--text-default)]">Your engagements</h1>
          <p className="mt-1 text-sm text-[var(--text-muted)]">
            Move from a grounded brief to a reviewed deliverable. Keep every advisory decision connected to evidence.
          </p>
        </div>
        <Button
          type="button"
          className="flex shrink-0 items-center gap-2"
          onClick={newEngagement}
        >
          <Plus size={16} aria-hidden />
          New engagement
        </Button>
      </header>

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4" aria-label="Engagement summary">
        {stats.isPending
          ? [0, 1, 2, 3].map((i) => (
              <div key={i} className="space-y-2 border border-[var(--surface-border)] bg-white p-4">
                <Skeleton className="h-4 w-2/3" />
                <Skeleton className="h-8 w-1/3" />
                <Skeleton className="h-3 w-1/2" />
              </div>
            ))
          : (stats.data ?? []).map((stat) => <EngagementStatCard key={stat.id} {...stat} />)}
      </section>

      <section className="space-y-3">
        <div className="flex flex-wrap items-center gap-3">
          <div className="relative min-w-[260px] flex-1">
            <Search
              size={16}
              className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-[var(--text-muted)]"
              aria-hidden
            />
            <Input
              value={query}
              onChange={(e) => {
                setQuery(e.target.value);
                setPage(1);
              }}
              placeholder="Search engagements or owners"
              className="pl-9"
            />
          </div>
          <Select
            aria-label="Status"
            value={status}
            onChange={(e) => {
              setStatus(e.target.value as EngagementListFilters["status"]);
              setPage(1);
            }}
            className="w-auto"
          >
            <option value="active">Status: Active</option>
            <option value="all">Status: All</option>
            <option value="archived">Status: Archived</option>
          </Select>
          <Button
            variant="secondary"
            type="button"
            aria-pressed={mine}
            className={`flex items-center gap-2 ${mine ? "border-[var(--accent-green)]" : ""}`}
            onClick={() => {
              setMine((prev) => !prev);
              setPage(1);
            }}
          >
            <SlidersHorizontal size={16} aria-hidden />
            {mine ? "Engagements I lead" : "My team"}
          </Button>
          <span className="ml-auto text-xs text-[var(--text-muted)]">
            Showing {rows.length} of {total} engagements
          </span>
        </div>

        {engagements.isPending ? (
          <div className="space-y-2" aria-busy>
            <Skeleton className="h-10 w-full" />
            <Skeleton className="h-16 w-full" />
            <Skeleton className="h-16 w-full" />
          </div>
        ) : rows.length === 0 ? (
          <EmptyState
            title={query ? "No engagements match your search" : "No engagements yet"}
            description={
              query
                ? "Try a different search term."
                : "Create your first engagement to start a conversation and generate deliverables."
            }
          >
            {!query ? (
              <Button type="button" onClick={newEngagement}>
                <Plus size={16} aria-hidden />
                New engagement
              </Button>
            ) : null}
          </EmptyState>
        ) : (
          <EngagementsTable rows={rows} />
        )}

        <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-[var(--text-muted)]">
          <span>Only engagements you have access to are shown.</span>
          <div className="flex items-center gap-3">
            <Button
              variant="ghost"
              type="button"
              disabled={page <= 1}
              onClick={() => setPage((prev) => prev - 1)}
              className="flex items-center gap-1 px-2 py-1 text-xs"
            >
              <ChevronLeft size={14} aria-hidden />
              Previous
            </Button>
            <span>
              {page} of {pageCount}
            </span>
            <Button
              variant="ghost"
              type="button"
              disabled={page >= pageCount}
              onClick={() => setPage((prev) => prev + 1)}
              className="flex items-center gap-1 px-2 py-1 text-xs"
            >
              Next
              <ChevronRight size={14} aria-hidden />
            </Button>
          </div>
        </div>
      </section>

      <section className="grid gap-4 lg:grid-cols-2">
        {nextActions.isPending ? (
          <Skeleton className="h-48 w-full" />
        ) : (
          <NextActionsPanel items={nextActions.data?.needsAction ?? []} />
        )}
        {recentActivity.isPending ? (
          <Skeleton className="h-48 w-full" />
        ) : (
          <RecentActivityPanel items={recentActivity.data ?? []} />
        )}
      </section>
    </main>
  );
}
