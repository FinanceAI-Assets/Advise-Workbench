"use client";

import { BookOpen, ChevronRight, Files } from "lucide-react";

import { LibraryBadge } from "@/components/admin-console/LibraryStatus";
import { DataTable, type DataTableColumn, DataTableToolbar, type DataTableState, INITIAL_TABLE_STATE } from "@/components/ui/DataTable";
import { EmptyState } from "@/components/ui/EmptyState";
import { cn } from "@/lib/utils";
import type { PracticeInventoryRow } from "@/types/api";

type LifecycleFilter = "all" | "published" | "review" | "draft";

/** Held by the page, so the search, filter, sort and page survive opening a practice and coming back. */
export type PracticeListState = { query: string; lifecycle: LifecycleFilter; table: DataTableState };

export const INITIAL_PRACTICE_LIST: PracticeListState = { query: "", lifecycle: "all", table: INITIAL_TABLE_STATE };

// The API reports approved releases as "Approved"; users see them as published.
const lifecycleLabel = (lifecycle: string) => (lifecycle === "Approved" ? "Published" : lifecycle);
const isPublished = (row: PracticeInventoryRow) => lifecycleLabel(row.lifecycle) === "Published";
const isDraft = (row: PracticeInventoryRow) => row.lifecycle === "Draft";
const isPending = (row: PracticeInventoryRow) => !isPublished(row) && !isDraft(row) && row.lifecycle !== "Not eligible";

const MATCHES: Record<LifecycleFilter, (row: PracticeInventoryRow) => boolean> = {
  all: () => true,
  published: isPublished,
  review: isPending,
  draft: isDraft,
};

/** "Benefits realization toolkit · LP-041" → title and code. */
function splitSource(practiceSource: string) {
  const [title, ...rest] = practiceSource.split(" · ");
  return { title, code: rest.join(" · ") };
}

const COLUMNS: DataTableColumn<PracticeInventoryRow>[] = [
  {
    key: "practice",
    header: "Practice",
    sortValue: (row) => splitSource(row.practiceSource).title,
    cell: (row) => {
      const { title, code } = splitSource(row.practiceSource);
      return (
        <span className="flex min-w-0 items-center gap-3">
          <span
            className={cn(
              "flex h-9 w-9 shrink-0 items-center justify-center rounded-md border",
              isDraft(row)
                ? "border-dashed border-[var(--surface-border-strong)] bg-white text-[var(--text-muted)]"
                : "border-[#D3E6BF] bg-[#EFF6E6] text-[var(--accent-green-dark)]"
            )}
            aria-hidden
          >
            <BookOpen size={16} />
          </span>
          <span className="min-w-0">
            <span className="block truncate font-semibold text-[var(--text-default)] group-hover:text-[var(--accent-green-dark)]" title={title}>
              {title}
            </span>
            <span className="block truncate text-xs text-[var(--text-muted)]">{code}</span>
          </span>
        </span>
      );
    },
  },
  {
    key: "sources",
    header: "Sources",
    width: "w-36",
    hideBelow: "sm",
    sortValue: (row) => row.sources ?? 0,
    cell: (row) => {
      const sources = row.sources ?? 0;
      return (
        <span className={cn("inline-flex items-center gap-1.5 text-sm", sources ? "text-[var(--text-default)]" : "text-[var(--text-muted)]")}>
          <Files size={14} className="text-[var(--text-muted)]" aria-hidden />
          <span className="font-semibold tabular-nums">{sources}</span>
          <span className="text-xs text-[var(--text-muted)]">source{sources === 1 ? "" : "s"}</span>
        </span>
      );
    },
  },
  {
    key: "status",
    header: "Status",
    width: "w-48",
    sortValue: (row) => lifecycleLabel(row.lifecycle),
    cell: (row) => <LibraryBadge dot>{lifecycleLabel(row.lifecycle)}</LibraryBadge>,
  },
  {
    key: "open",
    header: "",
    width: "w-10",
    align: "right",
    cell: () => (
      <ChevronRight
        size={16}
        className="inline text-[var(--text-muted)] transition-transform group-hover:translate-x-0.5 group-hover:text-[var(--accent-green-dark)]"
        aria-hidden
      />
    ),
  },
];

/** Every practice in the library: search, status filter and a sortable, paged table; each row opens that practice. */
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
    ...(rows.some(isDraft) ? [{ key: "draft" as const, label: "Drafts", count: rows.filter(isDraft).length }] : []),
  ];
  const needle = state.query.trim().toLowerCase();
  const visible = rows.filter((row) => MATCHES[state.lifecycle](row) && (!needle || row.practiceSource.toLowerCase().includes(needle)));
  const firstPage = { ...state.table, page: 1 };

  return (
    <div className="space-y-4">
      <DataTableToolbar
        search={state.query}
        onSearch={(query) => onChange({ ...state, query, table: firstPage })}
        searchLabel="Search practices"
        placeholder="Search by title or code"
        filters={filters}
        activeFilter={state.lifecycle}
        onFilter={(lifecycle) => onChange({ ...state, lifecycle, table: firstPage })}
        filterLabel="Status"
      />
      <DataTable
        label="Practices"
        itemName={visible.length === 1 ? "practice" : "practices"}
        columns={COLUMNS}
        rows={visible}
        rowKey={(row) => row.id}
        rowHref={(row) => hrefFor(row.id)}
        state={state.table}
        onStateChange={(table) => onChange({ ...state, table })}
        empty={
          <EmptyState
            title={rows.length === 0 ? "No practices yet" : "No practices match"}
            description={rows.length === 0 ? "Create a practice, then upload its sources." : "Try a different search or status."}
          />
        }
      />
    </div>
  );
}
