"use client";

import Link from "next/link";
import type { ReactNode } from "react";

import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorNote, PageFrame, PageSkeleton } from "@/components/workbench/PageFrame";
import { useEngagementsQuery } from "@/hooks/useEngagements";

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
  const engagements = useEngagementsQuery({ q: "", status: "active", mine: false, page: 1 });
  if (engagements.isPending) return <PageSkeleton />;
  const rows = engagements.data?.items ?? [];
  return (
    <PageFrame breadcrumb={`User workspace / ${title}`} title={title} subtitle={subtitle} actions={actions}>
      <ErrorNote error={engagements.error} />
      {children}
      {rows.length === 0 ? (
        <EmptyState title="No engagements yet" description="Create an engagement first.">
          <Link href="/engagements/new">Create an engagement</Link>
        </EmptyState>
      ) : (
        <Card className="divide-y divide-[var(--surface-border)] p-0">
          {rows.map((row) => (
            <Link
              key={row.id}
              href={`/engagements/${row.id}/${area}`}
              className="flex flex-wrap items-center justify-between gap-3 p-4 !no-underline hover:bg-[var(--surface-muted)]"
            >
              <div>
                <p className="text-sm font-semibold text-[var(--text-default)]">{row.name}</p>
                <p className="text-xs text-[var(--text-muted)]">
                  {row.code} · {row.type} · Lead: {row.owner}
                </p>
              </div>
              <Badge variant="secondary">{row.stage}</Badge>
            </Link>
          ))}
        </Card>
      )}
      {(engagements.data?.total ?? 0) > rows.length ? (
        <p className="text-xs text-[var(--text-muted)]">
          Showing the first {rows.length}. Open <Link href="/engagements">Engagements</Link> to see them all.
        </p>
      ) : null}
    </PageFrame>
  );
}
