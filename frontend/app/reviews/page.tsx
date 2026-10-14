"use client";

import Link from "next/link";
import { useState } from "react";

import { EngagementTabs } from "@/components/engagements";
import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorNote, PageFrame, PageSkeleton } from "@/components/workbench/PageFrame";
import { useReviewsQuery } from "@/hooks/useWorkbench";

type Scope = "mine" | "all";

const STATE_TONE: Record<string, "success" | "warning" | "secondary"> = {
  Approved: "success",
  "Changes requested": "warning",
};

// Review queue: what is waiting on the signed-in user, and every review they can see.
export default function ReviewsPage() {
  const reviews = useReviewsQuery();
  const [scope, setScope] = useState<Scope>("mine");

  if (reviews.isPending) return <PageSkeleton />;
  const all = reviews.data?.items ?? [];
  const mine = new Set(reviews.data?.mine ?? []);
  const rows = scope === "mine" ? all.filter((r) => mine.has(r.id)) : all;

  return (
    <PageFrame
      breadcrumb="User workspace / Reviews"
      title="Reviews"
      subtitle="Independent review of artifact versions. Approval is version-specific and cannot be given by the author."
    >
      <EngagementTabs
        tabs={[
          { key: "mine" as const, label: "Waiting on me", count: mine.size },
          { key: "all" as const, label: "All reviews", count: all.length },
        ]}
        active={scope}
        onChange={setScope}
      />
      <ErrorNote error={reviews.error} />
      {rows.length === 0 ? (
        <EmptyState
          title={scope === "mine" ? "Nothing is waiting on you" : "No reviews yet"}
          description="Submit a draft for review from an engagement's deliverables."
        />
      ) : (
        <Card className="overflow-x-auto p-0">
          <table className="w-full text-left text-sm">
            <thead className="bg-[var(--surface-muted)] text-xs text-[var(--text-muted)]">
              <tr>
                <th className="px-4 py-2 font-medium">Item / reference</th>
                <th className="px-4 py-2 font-medium">Engagement</th>
                <th className="px-4 py-2 font-medium">Type</th>
                <th className="px-4 py-2 font-medium">Owner</th>
                <th className="px-4 py-2 font-medium">Reviewer</th>
                <th className="px-4 py-2 font-medium">Due</th>
                <th className="px-4 py-2 font-medium">State</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.id} className="border-t border-[var(--surface-border)]">
                  <td className="px-4 py-3">
                    <Link href={`/reviews/${encodeURIComponent(row.id)}`} className="font-medium">
                      {row.title} · {row.id}
                    </Link>
                  </td>
                  <td className="px-4 py-3 text-[var(--text-muted)]">{row.engagement}</td>
                  <td className="px-4 py-3">{row.type}</td>
                  <td className="px-4 py-3">{row.owner}</td>
                  <td className="px-4 py-3">{row.reviewer}</td>
                  <td className="px-4 py-3">{row.dueDate}</td>
                  <td className="px-4 py-3">
                    <Badge variant={STATE_TONE[row.state] ?? "secondary"}>{row.state}</Badge>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}
    </PageFrame>
  );
}
