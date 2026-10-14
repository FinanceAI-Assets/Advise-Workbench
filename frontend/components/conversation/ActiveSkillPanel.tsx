import { LayoutGrid } from "lucide-react";

import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import { Select } from "@/components/ui/Select";
import type { ActiveSkill } from "@/types/api";

type SkillOption = { id: string; name: string; version: string };

export function ActiveSkillPanel({
  skill,
  options = [],
  selectedId,
  onChange,
}: {
  skill: ActiveSkill;
  options?: SkillOption[];
  selectedId?: string;
  onChange?: (skillId: string) => void;
}) {
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
      {onChange && options.length > 1 ? (
        <label className="grid gap-1.5 text-2xs font-semibold uppercase tracking-wide text-[var(--text-muted)]">
          Change skill
          <Select value={selectedId} onChange={(e) => onChange(e.target.value)}>
            {options.map((option) => (
              <option key={option.id} value={option.id}>
                {option.name} {option.version}
              </option>
            ))}
          </Select>
        </label>
      ) : null}
    </Card>
  );
}
