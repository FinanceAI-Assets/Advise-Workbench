"use client";

import { ChevronLeft, ChevronRight, Search } from "lucide-react";
import Link from "next/link";

import { LibraryBadge } from "@/components/admin-console/LibraryStatus";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { Input } from "@/components/ui/Input";
import { cn } from "@/lib/utils";
import type { PracticeInventoryRow } from "@/types/api";

type LifecycleFilter = "all" | "published" | "review";

/** Held by the page, so the search, filter and page survive opening a practice and coming back. */
export type PracticeListState = { query: string; lifecycle: LifecycleFilter; page: number };

export const INITIAL_PRACTICE_LIST: PracticeListState = { query: "", lifecycle: "all", page: 1 };

const PAGE_SIZE = 10;

// Shared by the header and every row so the columns line up; below md only the title, lifecycle and arrow remain.
const COLUMNS =
  "grid grid-cols-[minmax(0,1fr)_auto_16px] items-center gap-x-4 md:grid-cols-[minmax(0,1fr)_128px_112px_148px_16px]";

// The API reports approved releases as "Approved"; users see them as published.
const lifecycleLabel = (lifecycle: string) => (lifecycle === "Approved" ? "Published" : lifecycle);
const isPublished = (row: PracticeInventoryRow) => lifecycleLabel(row.lifecycle) === "Published";
const isPending = (row: PracticeInventoryRow) => !isPublished(row) && row.lifecycle !== "Not eligible";

/** "Benefits realization toolkit · LP-041" → title and code. */
function splitSource(practiceSource: string) {
  const [title, ...rest] = practiceSource.split(" · ");
  return { title, code: rest.join(" · ") };
}

function PracticeRow({ row, href }: { row: PracticeInventoryRow; href: string }) {
  const { title, code } = splitSource(row.practiceSource);
  return (
    <li>
      <Link
        href={href}
        className={`group ${COLUMNS} px-4 py-3 !no-underline transition-colors hover:bg-[var(--surface-muted)] focus-visible:outline focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-[var(--accent-green)]`}
      >
        <span className="min-w-0">
          <span className="block truncate text-sm font-semibold text-[var(--text-default)]" title={title}>
            {title}
          </span>
          <span className="block truncate text-xs text-[var(--text-muted)]">{code}</span>
        </span>
        <span className="hidden truncate text-xs text-[var(--text-default)] md:block">{row.version}</span>
        <span className="hidden md:block">
          <LibraryBadge>{row.indexing}</LibraryBadge>
        </span>
        <span>
          <LibraryBadge>{lifecycleLabel(row.lifecycle)}</LibraryBadge>
        </span>
        <ChevronRight
          size={16}
          className="text-[var(--text-muted)] transition-transform group-hover:translate-x-0.5 group-hover:text-[var(--accent-green-dark)]"
          aria-hidden
        />
      </Link>
    </li>
  );
}

/** Every practice in the library: search, lifecycle filter and a paged list; each row opens that practice. */
export function PracticeInventoryPanel({
  rows,
  state,
  onChange,
  hrefFor,
}: {
  rows: PracticeInventoryRow[];
  state: PracticeListState;
  onChange: (next: PracticeListState) => void;
  hrefFor: (id: string) => string;
}) {
  const filters: Array<{ key: LifecycleFilter; label: string; count: number }> = [
    { key: "all", label: "All", count: rows.length },
    { key: "published", label: "Published", count: rows.filter(isPublished).length },
    { key: "review", label: "In review", count: rows.filter(isPending).length },
  ];

  const needle = state.query.trim().toLowerCase();
  const visible = rows.filter(
    (row) =>
      (state.lifecycle === "all" || (state.lifecycle === "published" ? isPublished(row) : isPending(row))) &&
      (!needle || `${row.practiceSource} ${row.version}`.toLowerCase().includes(needle))
  );
  const pageCount = Math.max(1, Math.ceil(visible.length / PAGE_SIZE));
  // A delete can leave the remembered page past the end of the list.
  const page = Math.min(state.page, pageCount);
  const pageRows = visible.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="relative min-w-[260px] max-w-md flex-1">
          <Search
            size={16}
            className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-[var(--text-muted)]"
            aria-hidden
          />
          <Input
            type="search"
            aria-label="Search practices"
            value={state.query}
            onChange={(e) => onChange({ ...state, query: e.target.value, page: 1 })}
            placeholder="Search by title, code or version"
            className="pl-9"
          />
        </div>
        <div className="flex items-center gap-1" role="group" aria-label="Lifecycle">
          {filters.map((filter) => (
            <Button
              key={filter.key}
              type="button"
              variant="ghost"
              aria-pressed={state.lifecycle === filter.key}
              onClick={() => onChange({ ...state, lifecycle: filter.key, page: 1 })}
              className={cn(
                "whitespace-nowrap px-3 py-1.5 text-xs font-medium",
                state.lifecycle === filter.key
                  ? "bg-[#EFF6E6] text-[var(--accent-green-dark)] hover:bg-[#EFF6E6]"
                  : "text-[var(--text-muted)] hover:text-[var(--text-default)]"
              )}
            >
              {filter.label} · {filter.count}
            </Button>
          ))}
        </div>
      </div>

      {visible.length === 0 ? (
        <EmptyState
          title={rows.length === 0 ? "No practices yet" : "No practices match"}
          description={rows.length === 0 ? "Upload a source to start a candidate practice." : "Try a different search or lifecycle."}
        />
      ) : (
        <Card className="overflow-hidden p-0">
          <div
            className={`${COLUMNS} hidden border-b border-[var(--surface-border)] px-4 py-2.5 text-xs font-medium text-[var(--text-muted)] md:grid`}
            aria-hidden
          >
            <span>Practice</span>
            <span>Version</span>
            <span>Indexing</span>
            <span>Lifecycle</span>
          </div>
          <ul className="divide-y divide-[var(--surface-border)]" aria-label="Practices">
            {pageRows.map((row) => (
              <PracticeRow key={row.id} row={row} href={hrefFor(row.id)} />
            ))}
          </ul>
        </Card>
      )}

      {visible.length > 0 ? (
        <div className="flex items-center justify-between gap-3 text-xs text-[var(--text-muted)]">
          <span aria-live="polite">
            {visible.length} practice{visible.length === 1 ? "" : "s"}
          </span>
          {pageCount > 1 ? (
            <div className="flex items-center gap-3">
              <Button
                variant="ghost"
                type="button"
                disabled={page <= 1}
                onClick={() => onChange({ ...state, page: page - 1 })}
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
                onClick={() => onChange({ ...state, page: page + 1 })}
                className="flex items-center gap-1 px-2 py-1 text-xs"
              >
                Next
                <ChevronRight size={14} aria-hidden />
              </Button>
            </div>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
