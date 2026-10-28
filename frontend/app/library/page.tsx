"use client";

import { Bookmark, MessageSquareText, Plus, Search } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { LibraryAssistant, PracticeCard, PracticeDetailPanel, TaxonomyPanel } from "@/components/lp-library";
import { Button } from "@/components/ui/Button";
import { EmptyState } from "@/components/ui/EmptyState";
import { Input } from "@/components/ui/Input";
import { Select } from "@/components/ui/Select";
import { Skeleton } from "@/components/ui/Skeleton";
import { ErrorNote, PageFrame, PageSkeleton } from "@/components/workbench/PageFrame";
import { useEngagementsQuery } from "@/hooks/useEngagements";
import { type LibraryFilters, useLibraryQuery, usePracticeActions, usePracticeQuery } from "@/hooks/useWorkbench";

const INITIAL: LibraryFilters = { q: "", category: "all", maturity: "", sort: "relevance", savedOnly: false };

/** Detail of the selected practice with its two actions: save, and add to an engagement's sources. */
function PracticePanel({ id }: { id: string }) {
  const practice = usePracticeQuery(id);
  const actions = usePracticeActions(id);
  const engagements = useEngagementsQuery({ q: "", status: "active", mine: false, page: 1 });
  const [projectId, setProjectId] = useState("");
  const rows = engagements.data?.items ?? [];
  const target = projectId || rows[0]?.id || "";
  const added = actions.addToEngagement.data;

  if (practice.isPending) return <Skeleton className="h-96 w-full" />;
  if (!practice.data) return <ErrorNote error={practice.error} />;
  const saved = practice.data.saved;

  return (
    <PracticeDetailPanel
      practice={practice.data}
      actions={
        <div className="space-y-3 border-t border-[var(--surface-border)] pt-4">
          <label className="grid gap-1.5 text-2xs font-semibold uppercase tracking-wide text-[var(--text-muted)]">
            Add to an engagement&apos;s sources
            <Select value={target} onChange={(e) => setProjectId(e.target.value)}>
              {rows.map((row) => (
                <option key={row.id} value={row.id}>
                  {row.name} · {row.code}
                </option>
              ))}
            </Select>
          </label>
          <div className="flex flex-wrap gap-2">
            <Button
              className="flex items-center gap-2"
              disabled={!target || actions.addToEngagement.isPending}
              onClick={() => actions.addToEngagement.mutate(target)}
            >
              <Plus size={16} aria-hidden />
              Add to engagement
            </Button>
            <Button
              variant="secondary"
              className="flex items-center gap-2"
              disabled={actions.save.isPending}
              onClick={() => actions.save.mutate(!saved)}
            >
              <Bookmark size={16} aria-hidden />
              {saved ? "Remove from saved" : "Save practice"}
            </Button>
          </div>
          {added ? (
            <p className="text-sm text-[#356B12]">
              {added.added ? "Added. Conversations in that engagement can now cite it." : "Already in that engagement's sources."}
            </p>
          ) : null}
          <ErrorNote error={actions.addToEngagement.error ?? actions.save.error} />
        </div>
      }
    />
  );
}

// Leading Practice Library: approved practices by taxonomy, with search, filters and saved practices.
export default function LibraryPage() {
  const [filters, setFilters] = useState<LibraryFilters>(INITIAL);
  const [selected, setSelected] = useState("");
  const [askOpen, setAskOpen] = useState(false);
  const closeAsk = useCallback(() => setAskOpen(false), []);
  const library = useLibraryQuery(filters);
  const set = (change: Partial<LibraryFilters>) => setFilters((prev) => ({ ...prev, ...change }));

  // Links such as /library?practice=lp-016 open that practice.
  useEffect(() => {
    setSelected(new URLSearchParams(window.location.search).get("practice") ?? "");
  }, []);

  if (library.isPending && !library.data) return <PageSkeleton />;
  const data = library.data;
  const cards = data?.cards ?? [];
  const activeId = selected || cards[0]?.id || "";
  const filtered = filters.q || filters.maturity || filters.savedOnly || filters.category !== "all";

  return (
    <PageFrame
      breadcrumb="User workspace / Leading Practice Library"
      title={filters.savedOnly ? "My saved practices" : "Leading Practice Library"}
      subtitle={
        filters.savedOnly
          ? "Your personal collection of approved guidance. Saving a practice does not change its access rules."
          : "Approved, versioned guidance you can cite in engagement conversations."
      }
      actions={
        <div className="flex flex-wrap gap-2">
          <Button variant="secondary" className="flex items-center gap-2" onClick={() => setAskOpen((open) => !open)} aria-pressed={askOpen}>
            <MessageSquareText size={16} aria-hidden />
            Ask the Library
          </Button>
          <Button variant="secondary" className="flex items-center gap-2" onClick={() => set({ savedOnly: !filters.savedOnly })}>
            <Bookmark size={16} aria-hidden />
            {filters.savedOnly ? "All practices" : `My saved practices (${data?.savedCount ?? 0})`}
          </Button>
        </div>
      }
    >
      <ErrorNote error={library.error} />
      <div className="flex flex-wrap items-center gap-3">
        <div className="relative min-w-[260px] flex-1">
          <Search size={16} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-[var(--text-muted)]" aria-hidden />
          <Input value={filters.q} onChange={(e) => set({ q: e.target.value })} placeholder="Search practices" className="pl-9" />
        </div>
        <Select aria-label="Maturity" value={filters.maturity} onChange={(e) => set({ maturity: e.target.value })} className="w-auto">
          <option value="">Maturity: Any</option>
          {(data?.maturities ?? []).map((option) => (
            <option key={option}>{option}</option>
          ))}
        </Select>
        <Select aria-label="Sort" value={filters.sort} onChange={(e) => set({ sort: e.target.value })} className="w-auto">
          <option value="relevance">Sort: Catalog order</option>
          <option value="title">Sort: Title</option>
          <option value="updated">Sort: Recently updated</option>
        </Select>
        {filtered ? (
          <Button variant="ghost" onClick={() => setFilters(INITIAL)}>
            Clear filters
          </Button>
        ) : null}
        <span className="ml-auto text-xs text-[var(--text-muted)]">
          {data?.matchingCount ?? 0} of {data?.totalPractices ?? 0} approved practices
        </span>
      </div>

      <div className="grid gap-4 lg:grid-cols-[240px_1fr_420px]">
        <TaxonomyPanel
          categories={data?.categories ?? []}
          activeId={filters.category}
          onSelect={(category) => {
            set({ category });
            setSelected("");
          }}
        />
        <div className="space-y-3">
          {cards.length === 0 ? (
            <EmptyState
              title={filters.savedOnly ? "No saved practices yet" : "No practices match"}
              description={filters.savedOnly ? "Open a practice and choose Save practice." : "Try a different search or clear the filters."}
            />
          ) : (
            cards.map((card) => (
              <PracticeCard key={card.id} practice={card} active={card.id === activeId} onSelect={() => setSelected(card.id)} />
            ))
          )}
        </div>
        <div>{activeId ? <PracticePanel key={activeId} id={activeId} /> : null}</div>
      </div>
      {askOpen ? (
        <LibraryAssistant
          onClose={closeAsk}
          onOpenPractice={(id) => {
            // Show the practice even when the current filters hide its card.
            if (!cards.some((card) => card.id === id)) setFilters(INITIAL);
            setSelected(id);
          }}
        />
      ) : null}
    </PageFrame>
  );
}
