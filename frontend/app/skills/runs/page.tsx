"use client";

import Link from "next/link";

import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorNote, PageFrame, PageSkeleton } from "@/components/workbench/PageFrame";
import { useSkillRunsQuery } from "@/hooks/useWorkbench";

const TONE: Record<string, "success" | "warning" | "error" | "secondary"> = {
  done: "success",
  review_ready: "success",
  approved: "warning",
  plan_ready: "warning",
  failed: "error",
};

export default function SkillRunHistoryPage() {
  const runs = useSkillRunsQuery();
  if (runs.isPending) return <PageSkeleton />;
  const items = runs.data?.items ?? [];

  return (
    <PageFrame
      breadcrumb={
        <>
          User workspace / <Link href="/skills">Skills</Link> / Skill run history
        </>
      }
      title="Skill run history"
      subtitle="Runs across your engagements, with their outputs and status."
    >
      <ErrorNote error={runs.error} />
      {items.length === 0 ? (
        <EmptyState title="No runs yet" description="Run a skill in an engagement to see it here." />
      ) : (
        <Card className="overflow-x-auto p-0">
          <table className="w-full text-left text-sm">
            <thead className="bg-[var(--surface-muted)] text-xs text-[var(--text-muted)]">
              <tr>
                <th className="px-4 py-2 font-medium">Run</th>
                <th className="px-4 py-2 font-medium">Engagement</th>
                <th className="px-4 py-2 font-medium">Skill</th>
                <th className="px-4 py-2 font-medium">Outputs</th>
                <th className="px-4 py-2 font-medium">Date</th>
                <th className="px-4 py-2 font-medium">Status</th>
              </tr>
            </thead>
            <tbody>
              {items.map((run) => (
                <tr key={run.id} className="border-t border-[var(--surface-border)] align-top">
                  <td className="px-4 py-3">
                    <Link href={`/engagements/${run.projectId}/deliverables`} className="font-medium">
                      {run.id}
                    </Link>
                    <p className="text-xs text-[var(--text-muted)]">{run.instruction}</p>
                  </td>
                  <td className="px-4 py-3">{run.engagement}</td>
                  <td className="px-4 py-3">{run.skill}</td>
                  <td className="px-4 py-3">{run.outputs}</td>
                  <td className="px-4 py-3">{run.when}</td>
                  <td className="px-4 py-3">
                    <Badge variant={TONE[run.status] ?? "secondary"}>{run.status.replaceAll("_", " ")}</Badge>
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
