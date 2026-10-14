import type { ReactNode } from "react";
import { AlertCircle } from "lucide-react";

import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import { NoticeCard } from "@/components/ui/NoticeCard";
import type { TestResultsDetail } from "@/types/api";

export function TestResultsPanel({ results, actions }: { results: TestResultsDetail; actions?: ReactNode }) {
  return (
    <Card className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-base font-semibold text-[var(--text-default)]">Test results</h2>
        <span className="text-xs text-[var(--text-muted)]">{results.id.toUpperCase()}</span>
      </div>

      <div className="flex items-center justify-between">
        <p className="text-3xl font-semibold text-[var(--text-default)]">
          {results.passCount} / {results.totalCount}
        </p>
        <Badge className="border-[var(--surface-border)] bg-[#FBEFEB] text-[#A53E37]">{results.failLabel}</Badge>
      </div>
      <p className="text-xs text-[var(--text-muted)]">{results.runMeta}</p>

      <ul className="space-y-2">
        {results.checklist.map((row) => (
          <li key={row.id} className="flex items-center justify-between text-sm">
            <span className="text-[var(--text-default)]">{row.label}</span>
            <span className="font-medium text-[#356B12]">{row.state}</span>
          </li>
        ))}
      </ul>

      {results.failure ? (
        <NoticeCard
          tone="error"
          icon={<AlertCircle size={18} aria-hidden />}
          title={results.failure.title}
          description={results.failure.description}
        />
      ) : null}

      {actions}
    </Card>
  );
}
