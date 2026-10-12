"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";

import { EngagementProgressBar } from "@/components/engagements/EngagementProgressBar";
import { EngagementStageBadge } from "@/components/engagements/EngagementStageBadge";
import { cn } from "@/lib/utils";
import type { EngagementRow } from "@/types/api";

export function EngagementsTable({ rows }: { rows: EngagementRow[] }) {
  const router = useRouter();

  return (
    <div className="overflow-x-auto rounded-lg border border-[var(--surface-border)] bg-white">
      <table className="w-full min-w-[720px] text-left text-sm">
        <thead>
          <tr className="border-b border-[var(--surface-border)] text-xs text-[var(--text-muted)]">
            <th className="px-4 py-3 font-medium">Engagement</th>
            <th className="px-4 py-3 font-medium">Stage</th>
            <th className="px-4 py-3 font-medium">Progress</th>
            <th className="px-4 py-3 font-medium">Owner</th>
            <th className="px-4 py-3 font-medium">Next task</th>
            <th className="px-4 py-3 font-medium">Due</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr
              key={row.id}
              onClick={() => router.push(`/engagements/${row.id}`)}
              className={cn(
                "cursor-pointer border-b border-[var(--surface-border)] last:border-b-0 hover:bg-[var(--surface-muted)]",
                i === 0 && "border-l-2 border-l-[var(--accent-green)] bg-[#EFF6E6] hover:bg-[#EFF6E6]"
              )}
            >
              <td className="px-4 py-3">
                <Link
                  href={`/engagements/${row.id}`}
                  onClick={(e) => e.stopPropagation()}
                  className="!text-inherit !no-underline"
                >
                  <p className="font-semibold text-[var(--text-default)]">{row.name}</p>
                  <p className="text-xs text-[var(--text-muted)]">
                    {row.code} · {row.type}
                  </p>
                </Link>
              </td>
              <td className="px-4 py-3">
                <EngagementStageBadge stage={row.stage} />
              </td>
              <td className="px-4 py-3">
                <EngagementProgressBar value={row.progress} />
              </td>
              <td className="px-4 py-3 text-[var(--text-default)]">{row.owner}</td>
              <td className="px-4 py-3 text-[var(--text-default)]">{row.nextTask}</td>
              <td className="px-4 py-3 text-[var(--text-muted)]">{row.dueDate}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
