"use client";

import Link from "next/link";
import { useState } from "react";

import { EngagementTabs } from "@/components/engagements";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorNote, PageFrame, PageSkeleton } from "@/components/workbench/PageFrame";
import { type NotificationFilter, useNotificationActions, useNotificationsQuery } from "@/hooks/useWorkbench";

const KIND_LABEL: Record<string, string> = { mention: "Mention", review: "Review", system: "System" };

export default function NotificationsPage() {
  const [filter, setFilter] = useState<NotificationFilter>("all");
  const notifications = useNotificationsQuery(filter);
  const { read, readAll } = useNotificationActions();

  if (notifications.isPending) return <PageSkeleton />;
  const counts = notifications.data?.counts ?? { all: 0, unread: 0, mentions: 0, system: 0 };
  const items = notifications.data?.items ?? [];

  return (
    <PageFrame
      breadcrumb="User workspace / Header / Notifications"
      title="Notifications"
      subtitle="Review assignments, mentions and source-processing updates that need your attention."
      actions={
        <Button variant="secondary" disabled={counts.unread === 0 || readAll.isPending} onClick={() => readAll.mutate()}>
          Mark all as read
        </Button>
      }
    >
      <EngagementTabs
        tabs={[
          { key: "all" as const, label: "All", count: counts.all },
          { key: "unread" as const, label: "Unread", count: counts.unread },
          { key: "mentions" as const, label: "Mentions", count: counts.mentions },
          { key: "system" as const, label: "System", count: counts.system },
        ]}
        active={filter}
        onChange={setFilter}
      />
      <ErrorNote error={notifications.error ?? read.error ?? readAll.error} />
      {items.length === 0 ? (
        <EmptyState title="You're all caught up" description="Nothing to show for this filter." />
      ) : (
        <Card className="divide-y divide-[var(--surface-border)] p-0">
          {items.map((item) => (
            <div key={item.id} className={`flex flex-wrap items-start justify-between gap-3 p-4 ${item.read ? "" : "bg-[#EFF6E6]"}`}>
              <div className="min-w-0 flex-1">
                <p className="text-sm font-semibold text-[var(--text-default)]">
                  {item.title} <Badge variant="secondary">{KIND_LABEL[item.kind] ?? item.kind}</Badge>
                </p>
                <p className="text-xs text-[var(--text-muted)]">{item.when}</p>
                {item.body ? <p className="mt-1 text-sm text-[var(--text-default)]">{item.body}</p> : null}
              </div>
              <div className="flex shrink-0 items-center gap-2">
                {item.link ? (
                  <Link href={item.link} className="!no-underline" onClick={() => !item.read && read.mutate(item.id)}>
                    <Button variant="secondary" className="px-3 py-1.5 text-xs">
                      Open
                    </Button>
                  </Link>
                ) : null}
                {!item.read ? (
                  <Button variant="ghost" className="px-3 py-1.5 text-xs" onClick={() => read.mutate(item.id)}>
                    Mark read
                  </Button>
                ) : null}
              </div>
            </div>
          ))}
        </Card>
      )}
    </PageFrame>
  );
}
