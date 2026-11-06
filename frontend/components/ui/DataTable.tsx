"use client";

import { ArrowDown, ArrowUp, ArrowUpDown, ChevronLeft, ChevronRight, Search } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { type MouseEvent, type ReactNode, useState } from "react";

import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Skeleton } from "@/components/ui/Skeleton";
import { cn } from "@/lib/utils";

// The workbench's table: a bordered card with small uppercase headers, sortable columns, row links that work with
// the keyboard, and a pager. Use it for every list of records.

export type SortDirection = "asc" | "desc";

export type DataTableColumn<T> = {
  key: string;
  header: string;
  cell: (row: T) => ReactNode;
  /** Makes the column sortable by this value. */
  sortValue?: (row: T) => string | number | null | undefined;
  align?: "left" | "right" | "center";
  /** Tailwind width, e.g. "w-40". */
  width?: string;
  /** Hidden on narrow screens. */
  hideBelow?: "sm" | "md" | "lg";
};

export type DataTableState = { sort: { key: string; direction: SortDirection } | null; page: number; pageSize: number };

export const INITIAL_TABLE_STATE: DataTableState = { sort: null, page: 1, pageSize: 10 };

const PAGE_SIZES = [10, 25, 50];

const HIDE: Record<NonNullable<DataTableColumn<unknown>["hideBelow"]>, string> = {
  sm: "hidden sm:table-cell",
  md: "hidden md:table-cell",
  lg: "hidden lg:table-cell",
};

const ALIGN = { left: "text-left", right: "text-right", center: "text-center" } as const;

function compare(a: string | number | null | undefined, b: string | number | null | undefined) {
  a ??= "";
  b ??= "";
  return typeof a === "number" && typeof b === "number" ? a - b : String(a).localeCompare(String(b), undefined, { numeric: true, sensitivity: "base" });
}

/** "1 2 … 7 8 9 … 20": the first and last pages, and the pages around the current one. */
function pageList(page: number, count: number): Array<number | "gap"> {
  const pages = new Set([1, count, page - 1, page, page + 1].filter((p) => p >= 1 && p <= count));
  const sorted = [...pages].sort((a, b) => a - b);
  return sorted.flatMap((p, i) => (i > 0 && p - sorted[i - 1] > 1 ? (["gap", p] as const) : [p]));
}

/**
 * A sortable, paged table. Pass `state`/`onStateChange` to keep the sort and page when the user leaves and comes
 * back; without them the table keeps its own. With `rowHref` every row opens that page: the first cell is a real
 * link (keyboard, middle-click, open in new tab) and a click anywhere else on the row follows it too.
 */
export function DataTable<T>({
  label,
  columns,
  rows,
  rowKey,
  rowHref,
  onRowClick,
  isRowActive,
  state,
  onStateChange,
  loading = false,
  empty,
  itemName = "items",
  paginate = true,
  bare = false,
  minWidth,
}: {
  /** Accessible name of the table. */
  label: string;
  columns: DataTableColumn<T>[];
  rows: T[];
  rowKey: (row: T) => string;
  rowHref?: (row: T) => string;
  onRowClick?: (row: T) => void;
  isRowActive?: (row: T) => boolean;
  state?: DataTableState;
  onStateChange?: (next: DataTableState) => void;
  loading?: boolean;
  empty?: ReactNode;
  /** Plural noun for the summary: "Showing 1–10 of 27 practices". */
  itemName?: string;
  paginate?: boolean;
  /** No border of its own, for a table inside a Card that has its own title. */
  bare?: boolean;
  /** Tailwind min-width for wide tables, which then scroll sideways on narrow screens, e.g. "min-w-[900px]". */
  minWidth?: string;
}) {
  const router = useRouter();
  const [ownState, setOwnState] = useState(INITIAL_TABLE_STATE);
  const current = state ?? ownState;
  const setState = onStateChange ?? setOwnState;

  const sortColumn = current.sort ? columns.find((column) => column.key === current.sort?.key && column.sortValue) : undefined;
  const sorted =
    sortColumn?.sortValue && current.sort
      ? [...rows].sort((a, b) => compare(sortColumn.sortValue!(a), sortColumn.sortValue!(b)) * (current.sort!.direction === "asc" ? 1 : -1))
      : rows;
  const pageSize = paginate ? current.pageSize : Math.max(rows.length, 1);
  const pageCount = Math.max(1, Math.ceil(sorted.length / pageSize));
  // A filter or delete can leave the remembered page past the end.
  const page = Math.min(current.page, pageCount);
  const visible = sorted.slice((page - 1) * pageSize, page * pageSize);
  const first = sorted.length === 0 ? 0 : (page - 1) * pageSize + 1;

  const toggleSort = (key: string) => {
    const direction: SortDirection = current.sort?.key === key && current.sort.direction === "asc" ? "desc" : "asc";
    setState({ ...current, sort: { key, direction }, page: 1 });
  };

  const followRow = (event: MouseEvent<HTMLTableRowElement>, row: T) => {
    // Links, buttons and fields inside the row do their own thing.
    if ((event.target as HTMLElement).closest("a, button, input, select, textarea, label")) return;
    if (onRowClick) onRowClick(row);
    else if (rowHref) {
      if (event.metaKey || event.ctrlKey) window.open(rowHref(row), "_blank", "noopener");
      else router.push(rowHref(row));
    }
  };
  const clickable = Boolean(rowHref || onRowClick);

  return (
    <div className={cn("overflow-hidden bg-white", bare ? "border-t border-[var(--surface-border)]" : "rounded-lg border border-[var(--surface-border)]")}>
      <div className="overflow-x-auto">
        <table className={cn("w-full border-collapse text-left text-sm", minWidth)} aria-label={label} aria-busy={loading || undefined}>
          <thead className="bg-[var(--surface-muted)]">
            <tr className="border-b border-[var(--surface-border)]">
              {columns.map((column) => {
                const sortedBy = current.sort?.key === column.key ? current.sort.direction : null;
                const SortIcon = sortedBy === "asc" ? ArrowUp : sortedBy === "desc" ? ArrowDown : ArrowUpDown;
                return (
                  <th
                    key={column.key}
                    scope="col"
                    aria-sort={sortedBy ? (sortedBy === "asc" ? "ascending" : "descending") : undefined}
                    className={cn(
                      // Header size and weight are set here for every table (no global th rule).
                      "whitespace-nowrap px-4 py-3 text-xs font-bold uppercase tracking-wide text-[var(--text-default)]",
                      ALIGN[column.align ?? "left"],
                      column.width,
                      column.hideBelow && HIDE[column.hideBelow]
                    )}
                  >
                    {column.sortValue ? (
                      <button
                        type="button"
                        onClick={() => toggleSort(column.key)}
                        className={cn(
                          "-mx-1 inline-flex items-center gap-1.5 rounded px-1 py-0.5 font-bold uppercase tracking-wide hover:text-[var(--accent-green-dark)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--accent-green)]",
                          sortedBy && "text-[var(--accent-green-dark)]"
                        )}
                      >
                        {column.header}
                        <SortIcon size={14} aria-hidden className={sortedBy ? "text-[var(--accent-green-dark)]" : "opacity-40"} />
                      </button>
                    ) : (
                      <span className="uppercase tracking-wide">{column.header}</span>
                    )}
                  </th>
                );
              })}
            </tr>
          </thead>
          <tbody>
            {loading ? (
              Array.from({ length: 5 }, (_, i) => (
                <tr key={`loading-${i}`} className="border-b border-[var(--surface-border)] last:border-b-0">
                  {columns.map((column) => (
                    <td key={column.key} className={cn("px-4 py-4", column.hideBelow && HIDE[column.hideBelow])}>
                      <Skeleton className="h-4 w-3/4" />
                    </td>
                  ))}
                </tr>
              ))
            ) : visible.length === 0 ? (
              <tr>
                <td colSpan={columns.length} className="px-4 py-10">
                  {empty ?? <p className="text-center text-sm text-[var(--text-muted)]">Nothing to show.</p>}
                </td>
              </tr>
            ) : (
              visible.map((row) => {
                const active = isRowActive?.(row) ?? false;
                return (
                  <tr
                    key={rowKey(row)}
                    onClick={clickable ? (event) => followRow(event, row) : undefined}
                    aria-selected={isRowActive ? active : undefined}
                    className={cn(
                      "group border-b border-[var(--surface-border)] transition-colors last:border-b-0",
                      clickable && "cursor-pointer hover:bg-[var(--surface-muted)]",
                      active && "bg-[#EFF6E6] shadow-[inset_3px_0_0_var(--accent-green)] hover:bg-[#EFF6E6]"
                    )}
                  >
                    {columns.map((column, index) => (
                      <td
                        key={column.key}
                        className={cn("px-4 py-3 align-middle", ALIGN[column.align ?? "left"], column.width, column.hideBelow && HIDE[column.hideBelow])}
                      >
                        {index === 0 && rowHref ? (
                          <Link
                            href={rowHref(row)}
                            className="block !text-inherit !no-underline focus-visible:rounded focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--accent-green)]"
                          >
                            {column.cell(row)}
                          </Link>
                        ) : (
                          column.cell(row)
                        )}
                      </td>
                    ))}
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>

      {paginate && !loading && sorted.length > 0 ? (
        <div className="flex flex-wrap items-center justify-between gap-3 border-t border-[var(--surface-border)] px-4 py-2.5 text-xs text-[var(--text-muted)]">
          <div className="flex items-center gap-4">
            <span aria-live="polite">
              Showing <span className="font-semibold text-[var(--text-default)]">{first}–{first + visible.length - 1}</span> of{" "}
              <span className="font-semibold text-[var(--text-default)]">{sorted.length}</span> {itemName}
            </span>
            <label className="flex items-center gap-2">
              Rows per page
              <select
                value={current.pageSize}
                onChange={(event) => setState({ ...current, pageSize: Number(event.target.value), page: 1 })}
                className="rounded border border-[var(--surface-border)] bg-white px-1.5 py-1 text-xs text-[var(--text-default)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--accent-green)]"
              >
                {PAGE_SIZES.map((size) => (
                  <option key={size}>{size}</option>
                ))}
              </select>
            </label>
          </div>
          {pageCount > 1 ? (
            <nav className="flex items-center gap-1" aria-label={`${label} pages`}>
              <Button
                type="button"
                variant="ghost"
                disabled={page <= 1}
                aria-label="Previous page"
                className="p-1.5"
                onClick={() => setState({ ...current, page: page - 1 })}
              >
                <ChevronLeft size={14} aria-hidden />
              </Button>
              {pageList(page, pageCount).map((item, i) =>
                item === "gap" ? (
                  <span key={`gap-${i}`} className="px-1" aria-hidden>
                    …
                  </span>
                ) : (
                  <Button
                    key={item}
                    type="button"
                    variant="ghost"
                    aria-current={item === page ? "page" : undefined}
                    aria-label={`Page ${item}`}
                    onClick={() => setState({ ...current, page: item })}
                    className={cn(
                      "min-w-7 px-2 py-1 text-xs",
                      item === page ? "bg-[#EFF6E6] font-semibold text-[var(--accent-green-dark)] hover:bg-[#EFF6E6]" : "text-[var(--text-default)]"
                    )}
                  >
                    {item}
                  </Button>
                )
              )}
              <Button
                type="button"
                variant="ghost"
                disabled={page >= pageCount}
                aria-label="Next page"
                className="p-1.5"
                onClick={() => setState({ ...current, page: page + 1 })}
              >
                <ChevronRight size={14} aria-hidden />
              </Button>
            </nav>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

/** Search and quick filters above a DataTable; `actions` sit at the right end. */
export function DataTableToolbar<K extends string>({
  search,
  onSearch,
  searchLabel,
  placeholder,
  filters,
  activeFilter,
  onFilter,
  filterLabel = "Filter",
  actions,
}: {
  search: string;
  onSearch: (value: string) => void;
  searchLabel: string;
  placeholder: string;
  filters?: Array<{ key: K; label: string; count?: number }>;
  activeFilter?: K;
  onFilter?: (key: K) => void;
  filterLabel?: string;
  actions?: ReactNode;
}) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-3">
      <div className="relative min-w-[240px] max-w-md flex-1">
        <Search size={16} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-[var(--text-muted)]" aria-hidden />
        <Input type="search" aria-label={searchLabel} value={search} onChange={(e) => onSearch(e.target.value)} placeholder={placeholder} className="pl-9" />
      </div>
      <div className="flex flex-wrap items-center gap-3">
        {filters && onFilter ? (
          <div className="flex items-center rounded-md border border-[var(--surface-border)] bg-white p-0.5" role="group" aria-label={filterLabel}>
            {filters.map((filter) => {
              const active = filter.key === activeFilter;
              return (
                <button
                  key={filter.key}
                  type="button"
                  aria-pressed={active}
                  onClick={() => onFilter(filter.key)}
                  className={cn(
                    "flex items-center gap-1.5 whitespace-nowrap rounded px-3 py-1.5 text-xs font-medium transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--accent-green)]",
                    active ? "bg-[var(--accent-green)] text-white" : "text-[var(--text-muted)] hover:bg-[var(--surface-muted)] hover:text-[var(--text-default)]"
                  )}
                >
                  {filter.label}
                  {filter.count !== undefined ? (
                    <span
                      className={cn(
                        "rounded-full px-1.5 text-2xs leading-4",
                        active ? "bg-white/25 text-white" : "bg-[var(--surface-muted)] text-[var(--text-muted)]"
                      )}
                    >
                      {filter.count}
                    </span>
                  ) : null}
                </button>
              );
            })}
          </div>
        ) : null}
        {actions}
      </div>
    </div>
  );
}
