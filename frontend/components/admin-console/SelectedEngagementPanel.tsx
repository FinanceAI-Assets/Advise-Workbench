import { Archive, CalendarClock, UserCog } from "lucide-react";

import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import type { SelectedEngagementDetail } from "@/types/api";

function MetaField({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-2xs font-semibold uppercase tracking-wide text-[var(--text-muted)]">{label}</p>
      <p className="text-sm font-medium text-[var(--text-default)]">{value}</p>
    </div>
  );
}

export function SelectedEngagementPanel({ engagement }: { engagement: SelectedEngagementDetail }) {
  return (
    <Card className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-base font-semibold text-[var(--text-default)]">Selected: {engagement.name}</h2>
        <span className="text-xs text-[var(--text-muted)]">{engagement.code}</span>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <MetaField label="Access group" value={engagement.accessGroup} />
        <MetaField label="Content access" value={engagement.contentAccess} />
        <MetaField label="Retention policy" value={engagement.retentionPolicy} />
        <MetaField label="Scheduled disposition" value={engagement.scheduledDisposition} />
      </div>

      <table className="w-full text-left text-sm">
        <thead>
          <tr className="border-y border-[var(--surface-border)] bg-[var(--surface-muted)] text-xs text-[var(--text-muted)]">
            <th className="px-3 py-2 font-medium">Member</th>
            <th className="px-3 py-2 font-medium">Role</th>
            <th className="px-3 py-2 font-medium">Permission</th>
          </tr>
        </thead>
        <tbody>
          {engagement.members.map((member) => (
            <tr key={member.id} className="border-b border-[var(--surface-border)] last:border-b-0">
              <td className="px-3 py-2 font-medium text-[var(--text-default)]">{member.name}</td>
              <td className="px-3 py-2 text-[var(--text-muted)]">{member.role}</td>
              <td className="px-3 py-2 text-[var(--text-muted)]">{member.permission}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <div className="flex flex-wrap items-center gap-2">
        <Button variant="secondary" type="button" className="flex items-center gap-2 whitespace-nowrap text-sm">
          <UserCog size={16} aria-hidden />
          Manage access
        </Button>
        <Button variant="secondary" type="button" className="flex items-center gap-2 whitespace-nowrap text-sm">
          <CalendarClock size={16} aria-hidden />
          Adjust retention
        </Button>
        <Button variant="secondary" type="button" disabled className="flex items-center gap-2 whitespace-nowrap text-sm">
          <Archive size={16} aria-hidden />
          Archive
        </Button>
      </div>
    </Card>
  );
}
