import { ArrowRight } from "lucide-react";

import { Card } from "@/components/ui/Card";
import type { PracticeContext } from "@/types/api";

export function PracticeContextPanel({ practice }: { practice: PracticeContext }) {
  return (
    <Card className="space-y-3">
      <h2 className="text-base font-semibold text-[var(--text-default)]">Practice context</h2>
      <p className="font-semibold text-[var(--text-default)]">{practice.name}</p>
      <p className="text-sm text-[var(--text-muted)]">{practice.meta}</p>
      <a
        href={practice.practiceHref}
        className="inline-flex items-center gap-1 text-sm font-medium !text-[var(--accent-green-dark)] !no-underline hover:underline"
      >
        View practice
        <ArrowRight size={14} aria-hidden />
      </a>
    </Card>
  );
}
