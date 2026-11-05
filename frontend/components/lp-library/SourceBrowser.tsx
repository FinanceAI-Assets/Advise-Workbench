"use client";

import { Bookmark, Loader2, MessagesSquare, Plus, Search, ShieldCheck, X } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { AddResultNote, engagementSourcesPath } from "@/components/lp-library/AddResultNote";
import { PracticeDetailPanel } from "@/components/lp-library/PracticeDetailPanel";
import type { SelectedSource } from "@/components/lp-library/TalkToData";
import { TaxonomyPanel } from "@/components/lp-library/TaxonomyPanel";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Select } from "@/components/ui/Select";
import { Skeleton } from "@/components/ui/Skeleton";
import { ErrorNote } from "@/components/workbench/PageFrame";
import { useEngagementsQuery } from "@/hooks/useEngagements";
import {
  isLibraryFiltered,
  type LibraryFilters,
  useAddPracticesToEngagementMutation,
  useLibraryQuery,
  useMyEngagementOptionsQuery,
  usePracticeActions,
  usePracticeFetcher,
  usePracticeQuery,
} from "@/hooks/useWorkbench";
import { cn } from "@/lib/utils";

/** A practice checked on the source screen, waiting to be added to an engagement. */
export type BrowsePick = { id: string; title: string };

const INITIAL: LibraryFilters = { q: "", category: "all", maturity: "", sort: "relevance", savedOnly: false };

const SEARCH_DELAY_MS = 250;

// Same limit as AskLibrary.practice_ids on the API.
const MAX_CHAT_SOURCES = 20;

/**
 * Detail of a practice with its actions: save, and add to an engagement's sources. A selected practice offers deselect
 * instead of adding, since the selection bar adds all of them together.
 */
function PracticePanel({ id, onDeselect }: { id: string; onDeselect?: () => void }) {
  const practice = usePracticeQuery(id);
  const actions = usePracticeActions(id);
  const engagements = useEngagementsQuery({ q: "", status: "active", mine: false, page: 1 });
  const [projectId, setProjectId] = useState("");
  const rows = engagements.data?.items ?? [];
  const target = projectId || rows[0]?.id || "";
  const router = useRouter();

  if (practice.isPending) return <Skeleton className="h-96 w-full" />;
  if (!practice.data) return <ErrorNote error={practice.error} />;
  const saved = practice.data.saved;

  return (
    <PracticeDetailPanel
      practice={practice.data}
      actions={
        <div className="space-y-3 border-t border-[var(--surface-border)] pt-4">
          {onDeselect ? null : (
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
          )}
          <div className="flex flex-wrap gap-2">
            {onDeselect ? (
              <Button
                variant="secondary"
                className="flex items-center gap-2"
                aria-label={`Deselect ${practice.data.title}`}
                onClick={onDeselect}
              >
                <X size={16} aria-hidden />
                Deselect
              </Button>
            ) : (
              <Button
                className="flex items-center gap-2"
                disabled={!target || actions.addToEngagement.isPending}
                onClick={() => actions.addToEngagement.mutate(target, { onSuccess: () => router.push(engagementSourcesPath(target)) })}
              >
                <Plus size={16} aria-hidden />
                Add this practice
              </Button>
            )}
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
          <ErrorNote error={actions.addToEngagement.error ?? actions.save.error} />
        </div>
      }
    />
  );
}

/**
 * The source screen behind the chat's Browse sources button: a large search that, once used, opens onto categories on
 * the left, results in the middle and details on the right: of every checked source, or of the opened practice while
 * none is checked. Checked sources are either added to an engagement's sources or taken to the library chat.
 * Neither opens or changes an engagement conversation.
 */
export function SourceBrowser({
  picks,
  setPicks,
  initialPractice,
  chatSourceIds,
  onContinue,
}: {
  picks: BrowsePick[];
  setPicks: (update: (prev: BrowsePick[]) => BrowsePick[]) => void;
  initialPractice: string;
  chatSourceIds: string[];
  onContinue: (sources: SelectedSource[]) => void;
}) {
  const [filters, setFilters] = useState<LibraryFilters>(INITIAL);
  const [search, setSearch] = useState("");
  const [openId, setOpenId] = useState(initialPractice);
  const [projectId, setProjectId] = useState("");
  const [continuing, setContinuing] = useState(false);
  const [continueError, setContinueError] = useState<unknown>(null);
  const detailRef = useRef<HTMLDivElement>(null);
  const router = useRouter();
  const library = useLibraryQuery(filters);
  const engagements = useMyEngagementOptionsQuery();
  const addPractices = useAddPracticesToEngagementMutation();
  const fetchPractice = usePracticeFetcher();
  const data = library.data;
  // Nothing lists until there is something to list by; the debounced filter, so the first letter cannot show it all.
  const listing = isLibraryFiltered(filters);
  const cards = listing ? (data?.cards ?? []) : [];
  const rows = engagements.data?.items ?? [];
  const target = projectId || rows[0]?.id || "";
  const checkedIds = new Set(picks.map((p) => p.id));
  const set = (change: Partial<LibraryFilters>) => setFilters((prev) => ({ ...prev, ...change }));
  const settling = search.trim() !== filters.q || library.isPlaceholderData;
  // The practice opened while it is still listed (a linked one regardless). With nothing checked the first result
  // stands in for it; with sources checked only one the person clicked joins their details.
  const openStillShown = openId && (openId === initialPractice || cards.some((card) => card.id === openId));
  const previewId = picks.length
    ? (openStillShown && !checkedIds.has(openId) ? openId : "")
    : (openStillShown ? openId : (cards[0]?.id ?? ""));
  const focusedId = previewId || (checkedIds.has(openId) ? openId : "");

  useEffect(() => {
    const q = search.trim();
    // A new search starts from everything that matches; a category then narrows it. Emptying the box leaves the search.
    const timer = setTimeout(
      () =>
        setFilters((prev) =>
          prev.q === q ? prev : { ...prev, q, category: "all", maturity: q ? prev.maturity : "" }
        ),
      SEARCH_DELAY_MS
    );
    return () => clearTimeout(timer);
  }, [search]);

  const openPractice = (id: string) => {
    setOpenId(id);
    const column = detailRef.current;
    const selectedCard = column?.querySelector(`[data-practice="${CSS.escape(id)}"]`);
    if (selectedCard) selectedCard.scrollIntoView({ behavior: "smooth", block: "nearest" });
    // Below the three-column width the details sit under the results, so bring them into view.
    else if (!window.matchMedia("(min-width: 1280px)").matches) column?.scrollIntoView({ behavior: "smooth" });
    else column?.scrollTo({ top: 0, behavior: "smooth" });
  };

  const toggle = ({ id, title }: BrowsePick) => {
    addPractices.reset();
    setContinueError(null);
    // The newest details go on top of the column, so a tick shows at once.
    if (!checkedIds.has(id)) {
      setOpenId("");
      detailRef.current?.scrollTo({ top: 0 });
    }
    setPicks((prev) => (prev.some((p) => p.id === id) ? prev.filter((p) => p.id !== id) : [...prev, { id, title }]));
  };

  // The chat's selection carries each practice's code, version and owner, which a search result does not have.
  const continueWithChat = async () => {
    const total = new Set([...chatSourceIds, ...picks.map((p) => p.id)]).size;
    if (total > MAX_CHAT_SOURCES) {
      setContinueError(new Error(`The chat can answer from at most ${MAX_CHAT_SOURCES} sources at a time. Remove ${total - MAX_CHAT_SOURCES}.`));
      return;
    }
    setContinuing(true);
    setContinueError(null);
    try {
      const details = await Promise.all(picks.map((pick) => fetchPractice(pick.id)));
      onContinue(
        details.map((detail, i) => ({
          practiceId: picks[i].id,
          code: detail.code || picks[i].id.toUpperCase(),
          title: detail.title || picks[i].title,
          section: "",
          passage: detail.coreGuidance[0] ?? detail.description,
          version: detail.versionLabel,
          owner: [detail.sourceAttribution, detail.practiceOwner].filter(Boolean).join(" · "),
          approved: detail.approvedMeta,
        }))
      );
    } catch (error) {
      setContinueError(error);
      setContinuing(false);
    }
  };

  // All added: on to the engagement's sources. Otherwise stay, with what could not be added still checked, so it can be
  // retried or sent to another engagement.
  const addToEngagement = () =>
    addPractices.mutate(
      { projectId: target, practiceIds: picks.map((p) => p.id) },
      {
        onSuccess: ({ failed }, { projectId: added }) => {
          setPicks((prev) => prev.filter((p) => failed.some((f) => f.id === p.id)));
          if (!failed.length) router.push(engagementSourcesPath(added));
        },
      }
    );

  const result = addPractices.data;
  const resultProject = addPractices.variables?.projectId ?? "";
  const resultName = rows.find((row) => row.id === resultProject)?.name ?? "the engagement";

  const clear = () => {
    setFilters(INITIAL);
    setSearch("");
  };

  const detailColumn = (
    <div
      ref={detailRef}
      className={cn(
        "scroll-mt-20 space-y-3",
        listing && "lg:col-start-2 xl:sticky xl:top-[72px] xl:col-start-auto xl:max-h-[calc(100vh-88px)] xl:overflow-y-auto",
        listing && (picks.length || result) && "xl:pb-24"
      )}
    >
      {previewId ? <PracticePanel key={previewId} id={previewId} /> : null}
      {picks.length ? (
        <h2 className="px-1 text-sm font-semibold text-[var(--text-default)]">
          Details of {picks.length} selected source{picks.length === 1 ? "" : "s"}
        </h2>
      ) : null}
      {[...picks].reverse().map((pick) => (
        <div key={pick.id} data-practice={pick.id} className="scroll-mt-20">
          <PracticePanel id={pick.id} onDeselect={() => toggle(pick)} />
        </div>
      ))}
      {previewId || picks.length ? null : (
        <p className="rounded-lg border border-dashed border-[var(--surface-border)] p-8 text-center text-sm text-[var(--text-muted)]">
          Choose a practice to see its detail.
        </p>
      )}
      <div className="flex gap-2 px-1 text-xs text-[var(--text-muted)]">
        <ShieldCheck size={16} className="mt-0.5 shrink-0 text-[var(--accent-green-dark)]" aria-hidden />
        <p>
          <span className="block font-semibold text-[var(--text-default)]">Use with context, not as a prescription</span>
          Practice recommendations are illustrative. Validate applicability against engagement evidence and sponsor objectives.
        </p>
      </div>
    </div>
  );

  return (
    <div className="space-y-4">
      <div className={cn("space-y-4", !listing && "mx-auto max-w-3xl")}>
        <div className="relative">
          <Search size={22} className="pointer-events-none absolute left-5 top-1/2 -translate-y-1/2 text-[var(--text-muted)]" aria-hidden />
          <Input
            autoFocus
            type="search"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search approved practices by topic, outcome or title"
            aria-label="Search sources"
            className="h-16 rounded-2xl pl-14 pr-14 text-lg shadow-sm"
          />
          {settling ? (
            <Loader2
              size={20}
              className="absolute right-5 top-1/2 -translate-y-1/2 animate-spin text-[var(--text-muted)]"
              aria-label="Searching"
            />
          ) : null}
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            aria-pressed={filters.savedOnly}
            onClick={() => set({ savedOnly: !filters.savedOnly })}
            className={cn(
              "flex h-10 items-center gap-1.5 rounded-md border px-3 text-sm font-medium transition",
              filters.savedOnly
                ? "border-[var(--accent-green)] bg-[#EFF6E6] text-[#356B12]"
                : "border-[var(--surface-border)] bg-white text-[var(--text-muted)] hover:border-[var(--accent-green)]"
            )}
          >
            <Bookmark size={14} aria-hidden />
            My saved practices · {data?.savedCount ?? 0}
          </button>
          {listing ? (
            <>
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
              <Button variant="ghost" onClick={clear}>
                Clear filters
              </Button>
              <span className="ml-auto text-sm text-[var(--text-muted)]" aria-live="polite">
                {data?.matchingCount ?? 0} of {data?.totalPractices ?? 0} approved practices
              </span>
            </>
          ) : null}
        </div>

        <ErrorNote error={library.error} />

        {listing ? null : (
          <p className="py-6 text-center text-sm text-[var(--text-muted)]">
            Start typing to find approved practices, then check as many as you need.
          </p>
        )}
      </div>

      {listing ? (
        <div className="grid items-start gap-4 lg:grid-cols-[200px_minmax(0,1fr)] xl:grid-cols-[210px_minmax(0,1fr)_380px]">
          <div className="lg:sticky lg:top-[72px]">
            {data ? (
              <TaxonomyPanel categories={data.categories} activeId={filters.category} onSelect={(category) => set({ category })} />
            ) : (
              <Skeleton className="h-64 w-full" />
            )}
          </div>

          {library.isPending || (library.isPlaceholderData && !cards.length) ? (
            <div className="space-y-2">
              <Skeleton className="h-24 w-full" />
              <Skeleton className="h-24 w-full" />
            </div>
          ) : cards.length === 0 ? (
            <p className="rounded-lg border border-dashed border-[var(--surface-border)] p-8 text-center text-sm text-[var(--text-muted)]">
              {filters.savedOnly
                ? "No saved practices yet. Open a practice and choose Save practice."
                : "No practices match. Try a different word or clear the filters."}
            </p>
          ) : (
            <ul className={cn("space-y-2", library.isPlaceholderData && "opacity-60")} aria-label="Search results">
              {cards.map((card) => {
                const checked = checkedIds.has(card.id);
                const open = card.id === focusedId;
                return (
                  <li
                    key={card.id}
                    className={cn(
                      "flex items-start rounded-lg border bg-white transition",
                      open && "ring-1 ring-[var(--accent-green)]",
                      checked || open ? "border-[var(--accent-green)]" : "border-[var(--surface-border)] hover:border-[var(--accent-green)]"
                    )}
                  >
                    <label className="shrink-0 cursor-pointer p-4 pr-3">
                      <input
                        type="checkbox"
                        className="mt-1 block h-4 w-4 accent-[var(--accent-green)]"
                        aria-label={`Select ${card.title}`}
                        checked={checked}
                        onChange={() => toggle(card)}
                      />
                    </label>
                    <button
                      type="button"
                      aria-current={open ? "true" : undefined}
                      onClick={() => openPractice(card.id)}
                      className="min-w-0 flex-1 py-4 pr-4 text-left"
                    >
                      <span className="block font-semibold text-[var(--text-default)]">{card.title}</span>
                      <span className="mt-0.5 line-clamp-2 block text-sm text-[var(--text-muted)]">{card.description}</span>
                      <span className="mt-1 block text-xs text-[var(--text-muted)]">
                        {[card.maturity, card.category, card.versionLabel].filter(Boolean).join(" · ")}
                      </span>
                    </button>
                  </li>
                );
              })}
            </ul>
          )}

          {detailColumn}
        </div>
      ) : previewId || picks.length ? (
        <div className="mx-auto max-w-3xl">{detailColumn}</div>
      ) : null}

      {picks.length || result ? (
        <div className="sticky bottom-4 z-10 space-y-2 rounded-lg border-2 border-[var(--accent-green)] bg-white p-3 shadow-sm">
          {picks.length ? (
            <div className="flex flex-wrap items-center gap-3">
              <span className="text-sm font-semibold text-[var(--text-default)]">
                {picks.length} source{picks.length === 1 ? "" : "s"} selected
              </span>
              <ul className="flex min-w-0 flex-1 flex-wrap gap-1.5" aria-label="Selected sources">
                {picks.map((pick) => (
                  <li
                    key={pick.id}
                    className="flex max-w-[240px] items-center gap-1 rounded-full bg-[#EFF6E6] py-0.5 pl-2.5 pr-1 text-2xs font-medium text-[#356B12]"
                  >
                    <span className="truncate" title={pick.title}>
                      {pick.title}
                    </span>
                    <button
                      type="button"
                      onClick={() => toggle(pick)}
                      aria-label={`Remove ${pick.title}`}
                      className="shrink-0 rounded-full p-0.5 hover:bg-white"
                    >
                      <X size={12} aria-hidden />
                    </button>
                  </li>
                ))}
              </ul>
              <Select
                aria-label="Engagement"
                value={target}
                onChange={(e) => setProjectId(e.target.value)}
                disabled={!rows.length}
                className="w-auto max-w-[260px]"
              >
                {rows.length ? null : <option value="">{engagements.isPending ? "Loading…" : "No active engagements"}</option>}
                {rows.map((row) => (
                  <option key={row.id} value={row.id}>
                    {row.name} · {row.code}
                  </option>
                ))}
              </Select>
              <Button
                type="button"
                onClick={addToEngagement}
                disabled={!target || addPractices.isPending}
                className="flex items-center gap-2"
              >
                <Plus size={16} aria-hidden />
                {addPractices.isPending ? "Adding…" : "Add to engagement"}
              </Button>
              <Button
                type="button"
                variant="secondary"
                onClick={() => void continueWithChat()}
                disabled={continuing}
                className="flex items-center gap-2"
              >
                <MessagesSquare size={16} aria-hidden />
                {continuing ? "Opening…" : "Continue with chat"}
              </Button>
            </div>
          ) : null}
          <ErrorNote error={continueError} />
          {result ? (
            <AddResultNote result={result} projectId={resultProject} projectName={resultName} failedHint="Not added, still selected:" />
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
