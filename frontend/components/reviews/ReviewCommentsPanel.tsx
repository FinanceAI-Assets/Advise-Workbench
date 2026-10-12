"use client";

import { useState } from "react";

import { EngagementTabs } from "@/components/engagements";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import type { ReviewComment } from "@/types/api";

type CommentTabKey = "open" | "resolved" | "all";

export function ReviewCommentsPanel({
  comments,
  openCount,
  resolvedCount,
}: {
  comments: ReviewComment[];
  openCount: number;
  resolvedCount: number;
}) {
  const [tab, setTab] = useState<CommentTabKey>("open");

  const visible = comments.filter((c) => {
    if (tab === "all") return true;
    if (tab === "open") return c.status === "Open";
    return c.status === "Resolved";
  });

  return (
    <Card className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-base font-semibold text-[var(--text-default)]">Review comments</h2>
        <span className="text-xs text-[var(--text-muted)]">
          {openCount} open · {resolvedCount} resolved
        </span>
      </div>

      <EngagementTabs
        tabs={[
          { key: "open" as const, label: "Open", count: openCount },
          { key: "resolved" as const, label: "Resolved", count: resolvedCount },
          { key: "all" as const, label: "All", count: comments.length },
        ]}
        active={tab}
        onChange={setTab}
      />

      <ul className="space-y-3">
        {visible.map((comment) => (
          <li key={comment.id} className="space-y-2 rounded-md bg-[var(--surface-muted)] p-3">
            <div className="flex items-start justify-between gap-2">
              <p className="text-sm font-semibold text-[var(--text-default)]">{comment.title}</p>
              <Badge
                className={
                  comment.status === "Open"
                    ? "shrink-0 border-[var(--surface-border)] bg-[#FCF3E2] text-[#8C5B12]"
                    : "shrink-0 border-[var(--surface-border)] bg-[#EFF6E6] text-[#356B12]"
                }
              >
                {comment.status}
              </Badge>
            </div>
            <p className="text-xs text-[var(--text-muted)]">{comment.attribution}</p>
            <p className="text-sm text-[var(--text-default)]">{comment.body}</p>
            <div className="flex items-center justify-between gap-2">
              <span className="text-xs text-[var(--text-muted)]">Reply with your change…</span>
              <Button variant="secondary" type="button" className="whitespace-nowrap text-xs">
                Mark addressed
              </Button>
            </div>
          </li>
        ))}
      </ul>
    </Card>
  );
}
