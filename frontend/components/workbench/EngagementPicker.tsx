"use client";

import { ChevronLeft, ChevronRight, Search } from "lucide-react";
import Link from "next/link";
import { type ReactNode, useState } from "react";

import { EngagementProgressBar } from "@/components/engagements/EngagementProgressBar";
import { EngagementStageBadge } from "@/components/engagements/EngagementStageBadge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { Input } from "@/components/ui/Input";
import { ErrorNote, PageFrame, PageSkeleton } from "@/components/workbench/PageFrame";
import { ENGAGEMENTS_PAGE_SIZE, useEngagementsQuery } from "@/hooks/useEngagements";
import type { EngagementRow } from "@/types/api";

// Shared by the header and every row so the columns line up; below md only the name, stage and arrow remain.
const COLUMNS =
  "grid grid-cols-[minmax(0,1fr)_auto_16px] items-center gap-x-4 md:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)_168px_96px_16px]";

function EngagementListRow({ row, href }: { row: EngagementRow; href: string }) {
  const hasNextTask = row.nextTask !== "—";
  return (
    <li>
      <Link
        href={href}
        className={`group ${COLUMNS} px-4 py-3 !no-underline transition-colors hover:bg-[var(--surface-muted)] focus-visible:outline focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-[var(--accent-green)]`}
      >
        <span className="flex min-w-0 items-center gap-3">
          <span
            className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-[#EFF6E6] text-2xs font-semibold text-[var(--accent-green-dark)]"
            aria-hidden
          >
            {row.code.split("-")[0]}
          </span>
          <span className="min-w-0">
            <span className="block truncate text-sm font-semibold text-[var(--text-default)]" title={row.name}>
              {row.name}
            </span>
            <span className="block truncate text-xs text-[var(--text-muted)]">
              {row.code} · {row.type} · Lead: {row.owner}
            </span>
          </span>
        </span>
        <span className="hidden min-w-0 md:block">
          <span
            className={`block truncate text-xs ${hasNextTask ? "text-[var(--text-default)]" : "text-[var(--text-muted)]"}`}
            title={hasNextTask ? row.nextTask : undefined}
          >
            {hasNextTask ? row.nextTask : "No next task"}
          </span>
          {row.dueDate !== "—" ? <span className="block text-xs text-[var(--text-muted)]">Due {row.dueDate}</span> : null}
        </span>
        <span className="hidden md:block">
          <EngagementProgressBar value={row.progress} />
        </span>
        <span>
          <EngagementStageBadge stage={row.stage} />
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

/** Sidebar "Conversation" and "Deliverables" outside an engagement: choose which engagement to open. */
export function EngagementPicker({
  area,
  title,
  subtitle,
  actions,
  children,
}: {
  area: "conversation" | "deliverables";
  title: string;
  subtitle: string;
  actions?: ReactNode;
  // Shown above the engagement list, e.g. the new conversation form.
  children?: ReactNode;
}) {
  const [query, setQuery] = useState("");
  const [page, setPage] = useState(1);
  const engagements = useEngagementsQuery({ q: query, status: "active", mine: false, page });
  if (engagements.isPending) return <PageSkeleton />;
  const rows = engagements.data?.items ?? [];
  const total = engagements.data?.total ?? 0;
  const pageCount = Math.max(1, Math.ceil(total / ENGAGEMENTS_PAGE_SIZE));
  const searching = Boolean(query.trim());
  return (
    <PageFrame breadcrumb={`User workspace / ${title}`} title={title} subtitle={subtitle} actions={actions}>
      <ErrorNote error={engagements.error} />
      {children}
      {total > 0 || searching ? (
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="relative min-w-[260px] max-w-md flex-1">
            <Search
              size={16}
              className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-[var(--text-muted)]"
              aria-hidden
            />
            <Input
              aria-label="Search engagements"
              value={query}
              onChange={(e) => {
                setQuery(e.target.value);
                setPage(1);
              }}
              placeholder="Search by name, code or lead"
              className="pl-9"
            />
          </div>
          <span className="text-xs text-[var(--text-muted)]" aria-live="polite">
            {total} engagement{total === 1 ? "" : "s"}
          </span>
        </div>
      ) : null}
      {engagements.isError ? null : rows.length === 0 ? (
        searching ? (
          <EmptyState title="No engagements match your search" description="Try a different name, code or lead." />
        ) : (
          <EmptyState title="No engagements yet" description="Create an engagement first.">
            <Link href="/engagements/new">Create an engagement</Link>
          </EmptyState>
        )
      ) : (
        <Card className="overflow-hidden p-0">
          <div
            className={`${COLUMNS} hidden border-b border-[var(--surface-border)] px-4 py-2.5 text-xs font-medium text-[var(--text-muted)] md:grid`}
            aria-hidden
          >
            <span>Engagement</span>
            <span>Next task</span>
            <span>Progress</span>
            <span>Stage</span>
          </div>
          <ul className="divide-y divide-[var(--surface-border)]">
            {rows.map((row) => (
              <EngagementListRow key={row.id} row={row} href={`/engagements/${row.id}/${area}`} />
            ))}
          </ul>
        </Card>
      )}
      {pageCount > 1 ? (
        <div className="flex items-center justify-end gap-3 text-xs text-[var(--text-muted)]">
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
      ) : null}
    </PageFrame>
  );
}
