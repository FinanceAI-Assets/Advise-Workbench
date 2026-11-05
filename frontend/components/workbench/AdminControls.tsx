"use client";

import { Download } from "lucide-react";
import { type ReactNode, useState } from "react";

import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Input } from "@/components/ui/Input";
import { ErrorNote } from "@/components/workbench/PageFrame";
import { type AdminAction, type AdminRecord, useAdminAction } from "@/hooks/useAdminConsole";
import { useAuth } from "@/lib/auth-context";
import { downloadFile } from "@/lib/workbenchApi";

/**
 * A button for one administrative change. Clicking it asks for the reason the server
 * records in the audit trail, with any extra fields the change needs.
 */
export function ReasonAction({
  label,
  build,
  children,
  disabled,
  hint,
  primary,
}: {
  label: string;
  build: (reason: string) => AdminAction;
  children?: ReactNode;
  disabled?: boolean;
  hint?: string;
  primary?: boolean;
}) {
  const action = useAdminAction();
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState("");

  if (!open) {
    return (
      <Button
        variant={primary ? undefined : "secondary"}
        type="button"
        disabled={disabled}
        title={disabled ? hint : undefined}
        className="whitespace-nowrap text-sm"
        onClick={() => setOpen(true)}
      >
        {label}
      </Button>
    );
  }

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    await action.mutateAsync(build(reason.trim()));
    setOpen(false);
    setReason("");
  }

  return (
    <form onSubmit={(e) => void onSubmit(e)} className="w-full space-y-2 rounded-md bg-[var(--surface-muted)] p-3">
      <p className="text-sm font-semibold text-[var(--text-default)]">{label}</p>
      {children}
      <label className="grid gap-1.5 text-2xs font-semibold uppercase tracking-wide text-[var(--text-muted)]">
        Reason (recorded in the audit trail)
        <Input required minLength={5} value={reason} onChange={(e) => setReason(e.target.value)} />
      </label>
      <ErrorNote error={action.error} />
      <div className="flex gap-2">
        <Button type="submit" disabled={action.isPending} className="text-sm">
          {action.isPending ? "Saving…" : "Confirm"}
        </Button>
        <Button type="button" variant="secondary" className="text-sm" onClick={() => setOpen(false)}>
          Cancel
        </Button>
      </div>
    </form>
  );
}

/** Download one of the console's CSV reports. */
export function ExportButton({ report, label }: { report: "engagements" | "audit" | "reviews"; label: string }) {
  const { api } = useAuth();
  const [error, setError] = useState<unknown>(null);
  return (
    <>
      <Button
        variant="secondary"
        type="button"
        className="flex items-center gap-2 whitespace-nowrap"
        onClick={() =>
          void downloadFile(api, `/api/admin/export/${report}.csv`, `advise-workbench-${report}.csv`).catch(setError)
        }
      >
        <Download size={16} aria-hidden />
        {label}
      </Button>
      <ErrorNote error={error} />
    </>
  );
}

/** Plain table for the console's list tabs. `columns` maps a record field to its heading. */
export function RecordsTable({
  title,
  columns,
  rows,
  empty,
  action,
}: {
  title: string;
  columns: Array<[field: string, heading: string]>;
  rows: AdminRecord[];
  empty: string;
  action?: (row: AdminRecord) => ReactNode;
}) {
  return (
    <Card className="space-y-3 overflow-x-auto">
      <h2 className="text-base font-semibold text-[var(--text-default)]">{title}</h2>
      {rows.length === 0 ? (
        <p className="text-sm text-[var(--text-muted)]">{empty}</p>
      ) : (
        <table className="w-full text-left text-sm">
          <thead className="text-xs text-[var(--text-muted)]">
            <tr>
              {columns.map(([field, heading]) => (
                <th key={field} className="py-2 pr-3 font-medium">
                  {heading}
                </th>
              ))}
              {action ? <th className="py-2 font-medium">Action</th> : null}
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.id} className="border-t border-[var(--surface-border)] align-top">
                {columns.map(([field], i) => (
                  <td key={field} className={`py-3 pr-3 ${i === 0 ? "font-medium text-[var(--text-default)]" : ""}`}>
                    {row[field] ?? "—"}
                  </td>
                ))}
                {action ? <td className="py-3">{action(row)}</td> : null}
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </Card>
  );
}
