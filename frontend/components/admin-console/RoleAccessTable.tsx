import { Card } from "@/components/ui/Card";
import type { RoleAccessRow } from "@/types/api";

export function RoleAccessTable({ rows }: { rows: RoleAccessRow[] }) {
  return (
    <Card className="space-y-3 overflow-hidden p-0">
      <div className="flex items-center justify-between p-4 pb-0">
        <h2 className="text-base font-semibold text-[var(--text-default)]">Role-based access</h2>
        <span className="text-xs text-[var(--text-muted)]">Least privilege</span>
      </div>
      <table className="w-full text-left text-sm">
        <thead>
          <tr className="border-y border-[var(--surface-border)] bg-[var(--surface-muted)] text-xs text-[var(--text-muted)]">
            <th className="px-4 py-2 font-medium">Role</th>
            <th className="px-4 py-2 font-medium">Allowed</th>
            <th className="px-4 py-2 font-medium">Restricted</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.id} className="border-b border-[var(--surface-border)] last:border-b-0">
              <td className="px-4 py-3 font-medium text-[var(--text-default)]">{row.role}</td>
              <td className="px-4 py-3 text-[var(--text-muted)]">{row.allowed}</td>
              <td className="px-4 py-3 text-[var(--text-muted)]">{row.restricted}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </Card>
  );
}
