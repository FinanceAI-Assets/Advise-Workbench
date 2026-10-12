"use client";

import { Badge } from "@/components/ui/Badge";
import { cn } from "@/lib/utils";
import type { AdminEngagementRow } from "@/types/api";

const CONTROL_STATE_CLASS: Record<string, string> = {
  "Export locked": "border-[var(--surface-border)] bg-[#FCF3E2] text-[#8C5B12]",
  "Review pending": "border-[var(--surface-border)] bg-[#FCF3E2] text-[#8C5B12]",
  "Access risk": "border-[var(--surface-border)] bg-[#FBEFEB] text-[#A53E37]",
  "Export permitted": "border-[var(--surface-border)] bg-[#EFF6E6] text-[#356B12]",
  "Brief stage": "border-[var(--surface-border)] bg-[var(--surface-muted)] text-[var(--text-muted)]",
};

export function AdminEngagementsTable({
  rows,
  activeId,
  onSelect,
}: {
  rows: AdminEngagementRow[];
  activeId: string;
  onSelect: (id: string) => void;
}) {
  return (
    <div className="overflow-x-auto rounded-lg border border-[var(--surface-border)] bg-white">
      <table className="w-full min-w-[900px] text-left text-sm">
        <thead>
          <tr className="border-b border-[var(--surface-border)] text-xs text-[var(--text-muted)]">
            <th className="px-4 py-3 font-medium">Engagement / ID</th>
            <th className="px-4 py-3 font-medium">Owner / access</th>
            <th className="px-4 py-3 font-medium">Classification</th>
            <th className="px-4 py-3 font-medium">Retention</th>
            <th className="px-4 py-3 font-medium">Deliverables</th>
            <th className="px-4 py-3 font-medium">Control state</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr
              key={row.id}
              onClick={() => onSelect(row.id)}
              className={cn(
                "cursor-pointer border-b border-[var(--surface-border)] last:border-b-0 hover:bg-[var(--surface-muted)]",
                row.id === activeId && "border-l-2 border-l-[var(--accent-green)] bg-[#EFF6E6] hover:bg-[#EFF6E6]"
              )}
            >
              <td className="px-4 py-3">
                <p className="font-semibold text-[var(--text-default)]">{row.name}</p>
                <p className="text-xs text-[var(--text-muted)]">{row.code}</p>
              </td>
              <td className="px-4 py-3 text-[var(--text-default)]">{row.ownerAccess}</td>
              <td className="px-4 py-3 text-[var(--text-muted)]">{row.classification}</td>
              <td className="px-4 py-3 text-[var(--text-muted)]">{row.retention}</td>
              <td className="px-4 py-3 text-[var(--text-muted)]">{row.deliverables}</td>
              <td className="px-4 py-3">
                <Badge className={cn("whitespace-nowrap", CONTROL_STATE_CLASS[row.controlState] ?? "border-[var(--surface-border)] bg-white text-[var(--text-muted)]")}>
                  {row.controlState}
                </Badge>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
