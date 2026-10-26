"use client";

import { Search } from "lucide-react";
import { useState } from "react";

import { LibraryBadge } from "@/components/admin-console/LibraryStatus";
import { Card } from "@/components/ui/Card";
import { Input } from "@/components/ui/Input";
import { Select } from "@/components/ui/Select";
import { cn } from "@/lib/utils";
import type { PracticeInventoryRow } from "@/types/api";

type LifecycleFilter = "all" | "published" | "review";

// The API reports approved releases as "Approved"; users see them as published.
const lifecycleLabel = (lifecycle: string) => (lifecycle === "Approved" ? "Published" : lifecycle);
const isPublished = (row: PracticeInventoryRow) => lifecycleLabel(row.lifecycle) === "Published";
const isPending = (row: PracticeInventoryRow) => !isPublished(row) && row.lifecycle !== "Not eligible";

/** "Benefits realization toolkit · LP-041" → title and code. */
function splitSource(practiceSource: string) {
  const [title, ...rest] = practiceSource.split(" · ");
  return { title, code: rest.join(" · ") };
}

/** Practice inventory card: counts, search, lifecycle filter and the selectable table. */
export function PracticeInventoryPanel({
  rows,
  activeId,
  onSelect,
}: {
  rows: PracticeInventoryRow[];
  activeId: string;
  onSelect: (id: string) => void;
}) {
  const [query, setQuery] = useState("");
  const [lifecycle, setLifecycle] = useState<LifecycleFilter>("all");

  const needle = query.trim().toLowerCase();
  const visible = rows.filter(
    (row) =>
      (lifecycle === "all" || (lifecycle === "published" ? isPublished(row) : !isPublished(row))) &&
      (!needle || `${row.practiceSource} ${row.version}`.toLowerCase().includes(needle))
  );

  return (
    <Card className="space-y-3">
      <div className="flex items-center justify-between gap-3">
        <h2 className="text-sm font-semibold text-[var(--text-default)]">Practice inventory</h2>
        <span className="text-2xs text-[var(--text-muted)]">
          {rows.filter(isPublished).length} approved · {rows.filter(isPending).length} pending
        </span>
      </div>

      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="relative w-full max-w-[400px]">
          <Search
            size={14}
            className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-[var(--text-muted)]"
            aria-hidden
          />
          <Input
            type="search"
            aria-label="Search practices"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search practice title, owner or version"
            className="h-8 py-1 pl-8 pr-10 text-xs"
          />
          <kbd className="pointer-events-none absolute right-2.5 top-1/2 -translate-y-1/2 font-sans text-2xs text-[var(--text-muted)]">
            ⌘K
          </kbd>
        </div>
        <Select
          aria-label="Lifecycle"
          value={lifecycle}
          onChange={(e) => setLifecycle(e.target.value as LifecycleFilter)}
          className="min-h-0 w-auto py-1.5 pl-3 pr-8 text-xs font-medium"
        >
          <option value="all">Lifecycle: All</option>
          <option value="published">Lifecycle: Published</option>
          <option value="review">Lifecycle: In review</option>
        </Select>
      </div>

      <div className="overflow-x-auto rounded-md border border-[var(--surface-border)]">
        <table className="w-full min-w-[560px] text-left">
          <thead>
            <tr className="border-b border-[var(--surface-border)] bg-[var(--surface-muted)] text-[var(--text-muted)]">
              <th className="px-3 font-medium">Practice / source</th>
              <th className="px-3 font-medium">Version</th>
              <th className="px-3 font-medium">Indexing</th>
              <th className="px-3 font-medium">Lifecycle</th>
            </tr>
          </thead>
          <tbody>
            {visible.map((row) => {
              const { title, code } = splitSource(row.practiceSource);
              const active = row.id === activeId;
              return (
                <tr
                  key={row.id}
                  onClick={() => onSelect(row.id)}
                  aria-selected={active}
                  className={cn(
                    "h-[60px] cursor-pointer border-b border-[var(--surface-border)] last:border-b-0",
                    active ? "bg-[#EFF6E6]" : "hover:bg-[var(--surface-muted)]"
                  )}
                >
                  <td className="px-3 text-[var(--text-default)]" title={code || undefined}>
                    {title}
                  </td>
                  <td className="px-3 text-[var(--text-default)]">{row.version}</td>
                  <td className="px-3">
                    <LibraryBadge>{row.indexing}</LibraryBadge>
                  </td>
                  <td className="px-3">
                    <LibraryBadge>{lifecycleLabel(row.lifecycle)}</LibraryBadge>
                  </td>
                </tr>
              );
            })}
            {visible.length === 0 ? (
              <tr>
                <td colSpan={4} className="px-3 text-center text-[var(--text-muted)]">
                  No practices match.
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>
    </Card>
  );
}
