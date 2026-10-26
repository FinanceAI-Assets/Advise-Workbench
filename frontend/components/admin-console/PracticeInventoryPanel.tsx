import { Badge } from "@/components/ui/Badge";
import { cn } from "@/lib/utils";
import type { PracticeInventoryRow } from "@/types/api";

const INDEXING_CLASS: Record<string, string> = {
  Indexed: "border-[var(--surface-border)] bg-[#EFF6E6] text-[#356B12]",
  "OCR failed": "border-[var(--surface-border)] bg-[#FBEFEB] text-[#A53E37]",
};

const LIFECYCLE_CLASS: Record<string, string> = {
  Published: "border-[var(--surface-border)] bg-[#EFF6E6] text-[#356B12]",
  "Quality review": "border-[var(--surface-border)] bg-[#FCF3E2] text-[#8C5B12]",
  "Not eligible": "border-[var(--surface-border)] bg-[var(--surface-muted)] text-[var(--text-muted)]",
};

export function PracticeInventoryTable({
  rows,
  activeId,
  onSelect,
}: {
  rows: PracticeInventoryRow[];
  activeId: string;
  onSelect: (id: string) => void;
}) {
  return (
    <div className="overflow-x-auto rounded-lg border border-[var(--surface-border)] bg-white">
      <table className="w-full min-w-[600px] text-left text-sm">
        <thead>
          <tr className="border-b border-[var(--surface-border)] text-xs text-[var(--text-muted)]">
            <th className="px-4 py-3 font-medium">Practice / source</th>
            <th className="px-4 py-3 font-medium">Version</th>
            <th className="px-4 py-3 font-medium">Indexing</th>
            <th className="px-4 py-3 font-medium">Lifecycle</th>
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
              <td className="px-4 py-3 font-medium text-[var(--text-default)]">{row.practiceSource}</td>
              <td className="px-4 py-3 text-[var(--text-muted)]">{row.version}</td>
              <td className="px-4 py-3">
                <Badge className={INDEXING_CLASS[row.indexing] ?? "border-[var(--surface-border)] bg-white text-[var(--text-muted)]"}>
                  {row.indexing}
                </Badge>
              </td>
              <td className="px-4 py-3">
                <Badge className={LIFECYCLE_CLASS[row.lifecycle] ?? "border-[var(--surface-border)] bg-white text-[var(--text-muted)]"}>
                  {row.lifecycle}
                </Badge>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
