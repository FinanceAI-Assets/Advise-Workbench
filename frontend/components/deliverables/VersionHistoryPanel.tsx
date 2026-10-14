import { History } from "lucide-react";

import { Card } from "@/components/ui/Card";
import { cn } from "@/lib/utils";
import type { VersionHistoryEntry } from "@/types/api";

export function VersionHistoryPanel({ versions }: { versions: VersionHistoryEntry[] }) {
  return (
    <Card className="space-y-4">
      <h2 className="text-base font-semibold text-[var(--text-default)]">Version history</h2>
      <ul className="space-y-3">
        {versions.map((v) => (
          <li key={v.id} className="flex items-start gap-3">
            <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-[var(--surface-muted)] text-[var(--text-muted)]">
              <History size={14} aria-hidden />
            </span>
            <div>
              <p className={cn("text-sm", v.current ? "font-semibold text-[var(--text-default)]" : "text-[var(--text-default)]")}>
                {v.version}
                {v.current ? " · Current" : ""}
              </p>
              <p className="text-xs text-[var(--text-muted)]">{v.meta}</p>
            </div>
          </li>
        ))}
      </ul>
      <p className="border-t border-[var(--surface-border)] pt-3 text-xs text-[var(--text-muted)]">
        Versions are immutable after approval.
      </p>
    </Card>
  );
}
