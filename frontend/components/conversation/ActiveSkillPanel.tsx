import { LayoutGrid } from "lucide-react";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import type { ActiveSkill } from "@/types/api";

export function ActiveSkillPanel({ skill }: { skill: ActiveSkill }) {
  return (
    <Card className="space-y-3">
      <h2 className="text-base font-semibold text-[var(--text-default)]">Active skill</h2>
      <div className="flex items-center gap-2">
        <LayoutGrid size={16} className="text-[var(--accent-green)]" aria-hidden />
        <p className="font-semibold text-[var(--text-default)]">{skill.name}</p>
      </div>
      <p className="text-sm text-[var(--text-muted)]">
        {skill.version} · {skill.meta}
      </p>
      <div className="flex flex-wrap gap-2">
        {skill.formats.map((f) => (
          <Badge key={f} className="border-[var(--surface-border)] bg-[var(--surface-muted)] text-[var(--text-muted)]">
            {f}
          </Badge>
        ))}
      </div>
      <Button variant="secondary" type="button" className="text-sm">
        Change skill
      </Button>
    </Card>
  );
}
