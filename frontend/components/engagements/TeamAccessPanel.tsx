import { User, UserCheck } from "lucide-react";

import { Card } from "@/components/ui/Card";
import type { TeamMember } from "@/types/api";

export function TeamAccessPanel({
  members,
  memberCount,
  note,
}: {
  members: TeamMember[];
  memberCount: number;
  note: string;
}) {
  return (
    <Card className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-base font-semibold text-[var(--text-default)]">Team &amp; access</h2>
        <span className="text-xs text-[var(--text-muted)]">{memberCount} members</span>
      </div>
      <ul className="space-y-3">
        {members.map((member, i) => {
          const Icon = i === 0 ? User : UserCheck;
          return (
            <li key={member.id} className="flex items-start gap-3">
              <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-[var(--surface-muted)] text-[var(--text-muted)]">
                <Icon size={16} aria-hidden />
              </span>
              <div>
                <p className="text-sm font-medium text-[var(--text-default)]">{member.name}</p>
                <p className="text-xs text-[var(--text-muted)]">{member.roleAndAccess}</p>
              </div>
            </li>
          );
        })}
      </ul>
      {note ? <p className="border-t border-[var(--surface-border)] pt-3 text-xs text-[var(--text-muted)]">{note}</p> : null}
    </Card>
  );
}
