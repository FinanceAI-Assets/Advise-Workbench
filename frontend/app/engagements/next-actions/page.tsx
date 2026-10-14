"use client";

import Link from "next/link";
import { useState } from "react";

import { EngagementTabs } from "@/components/engagements";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorNote, PageFrame, PageSkeleton } from "@/components/workbench/PageFrame";
import { useNextActionsQuery } from "@/hooks/useEngagements";
import { useAuth } from "@/lib/auth-context";
import type { NextActionBuckets } from "@/types/api";

type Bucket = keyof NextActionBuckets;

const EMPTY: Record<Bucket, string> = {
  needsAction: "Nothing needs your action right now.",
  upcoming: "No upcoming milestones are assigned to you.",
  completed: "Nothing completed yet.",
};

export default function NextActionsPage() {
  const { user } = useAuth();
  const actions = useNextActionsQuery();
  const [bucket, setBucket] = useState<Bucket>("needsAction");

  if (actions.isPending) return <PageSkeleton />;
  const data = actions.data ?? { needsAction: [], upcoming: [], completed: [] };
  const items = data[bucket];

  return (
    <PageFrame
      breadcrumb={
        <>
          User workspace / <Link href="/engagements">Engagements</Link> / Your next actions
        </>
      }
      title="Your next actions"
      subtitle={`Prioritized work assigned to ${user?.name ?? "you"} across your advisory engagements.`}
    >
      <EngagementTabs
        tabs={[
          { key: "needsAction" as const, label: "Needs action", count: data.needsAction.length },
          { key: "upcoming" as const, label: "Upcoming", count: data.upcoming.length },
          { key: "completed" as const, label: "Completed", count: data.completed.length },
        ]}
        active={bucket}
        onChange={setBucket}
      />
      <ErrorNote error={actions.error} />
      {items.length === 0 ? (
        <EmptyState title={EMPTY[bucket]} />
      ) : (
        <Card className="divide-y divide-[var(--surface-border)] p-0">
          {items.map((item) => (
            <div key={item.id} className="flex flex-wrap items-center justify-between gap-3 p-4">
              <div>
                <p className="text-sm font-semibold text-[var(--text-default)]">{item.title}</p>
                <p className="text-xs text-[var(--text-muted)]">{item.description}</p>
              </div>
              <div className="flex items-center gap-3">
                <Badge variant="warning" className="border-[var(--surface-border)] bg-[#FCF3E2] text-[#8C5B12]">
                  {item.due}
                </Badge>
                {item.href ? (
                  <Link href={item.href} className="!no-underline">
                    <Button variant="secondary" className="px-3 py-1.5 text-xs">
                      {item.actionLabel ?? "Open"}
                    </Button>
                  </Link>
                ) : null}
              </div>
            </div>
          ))}
        </Card>
      )}
    </PageFrame>
  );
}
