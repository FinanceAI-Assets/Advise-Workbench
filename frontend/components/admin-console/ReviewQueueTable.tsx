import { Badge } from "@/components/ui/Badge";
import { cn } from "@/lib/utils";
import type { ReviewQueueRow } from "@/types/api";

const STATE_CLASS: Record<string, string> = {
  "Changes requested": "border-[var(--surface-border)] bg-[#FCF3E2] text-[#8C5B12]",
  "Attribution gap": "border-[var(--surface-border)] bg-[#FCF3E2] text-[#8C5B12]",
  "Test failed": "border-[var(--surface-border)] bg-[#FBEFEB] text-[#A53E37]",
  "Blocked · High risk": "border-[var(--surface-border)] bg-[#FBEFEB] text-[#A53E37]",
};

export function ReviewQueueTable({
  rows,
  activeId,
  onSelect,
}: {
  rows: ReviewQueueRow[];
  activeId: string;
  onSelect: (id: string) => void;
}) {
  return (
    <div className="overflow-x-auto rounded-lg border border-[var(--surface-border)] bg-white">
      <table className="w-full min-w-[600px] text-left text-sm">
        <thead>
          <tr className="border-b border-[var(--surface-border)] text-xs text-[var(--text-muted)]">
            <th className="px-4 py-3 font-medium">Item / reference</th>
            <th className="px-4 py-3 font-medium">Reviewer</th>
            <th className="px-4 py-3 font-medium">Type</th>
            <th className="px-4 py-3 font-medium">State</th>
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
              <td className="px-4 py-3 font-medium text-[var(--text-default)]">{row.itemReference}</td>
              <td className="px-4 py-3 text-[var(--text-default)]">{row.reviewer}</td>
              <td className="px-4 py-3 text-[var(--text-muted)]">{row.type}</td>
              <td className="px-4 py-3">
                <Badge className={cn("whitespace-nowrap", STATE_CLASS[row.state] ?? "border-[var(--surface-border)] bg-white text-[var(--text-muted)]")}>
                  {row.state}
                </Badge>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
