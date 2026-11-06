"use client";

import { Download, Search } from "lucide-react";
import { type ReactNode, useState } from "react";

import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { DataTable, type DataTableColumn } from "@/components/ui/DataTable";
import { Input } from "@/components/ui/Input";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { ErrorNote } from "@/components/workbench/PageFrame";
import { type AdminAction, type AdminRecord, useAdminAction } from "@/hooks/useAdminConsole";
import { useAuth } from "@/lib/auth-context";
import { cn } from "@/lib/utils";
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
  className,
}: {
  label: string;
  build: (reason: string) => AdminAction;
  children?: ReactNode;
  disabled?: boolean;
  hint?: string;
  primary?: boolean;
  /** Extra classes for the closed-state button, e.g. a compact size. */
  className?: string;
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
        className={cn("whitespace-nowrap text-sm", className)}
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

// Fields shown as a status pill rather than text.
const STATUS_FIELDS = new Set(["state", "status", "severity", "controlState", "lifecycle", "outcome", "result"]);
// Severity sorts by rank, most severe first, not alphabetically.
const SEVERITY_RANK: Record<string, number> = { Critical: 0, High: 1, Medium: 2, Low: 3 };

/**
 * The console's list tabs: a titled card with a search box over a sortable, paged table. `columns` maps a record
 * field to its heading; status-like fields are shown as pills.
 */
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
  const [query, setQuery] = useState("");
  const needle = query.trim().toLowerCase();
  const visible = needle
    ? rows.filter((row) => columns.some(([field]) => String(row[field] ?? "").toLowerCase().includes(needle)))
    : rows;
  const tableColumns: DataTableColumn<AdminRecord>[] = [
    ...columns.map(([field, heading], i): DataTableColumn<AdminRecord> => ({
      key: field,
      header: heading,
      sortValue: (row) => (field === "severity" ? (SEVERITY_RANK[row[field]] ?? 9) : (row[field] ?? "")),
      cell: (row) =>
        STATUS_FIELDS.has(field) && row[field] ? (
          <StatusBadge>{row[field]}</StatusBadge>
        ) : (
          <span className={i === 0 ? "font-semibold text-[var(--text-default)]" : "text-[var(--text-default)]"}>{row[field] || "—"}</span>
        ),
    })),
    ...(action ? [{ key: "__action", header: "Action", align: "right" as const, cell: (row: AdminRecord) => action(row) }] : []),
  ];

  return (
    <Card className="overflow-hidden p-0">
      <div className="flex flex-wrap items-center justify-between gap-3 p-4">
        <h2 className="text-base font-semibold text-[var(--text-default)]">
          {title} <span className="text-sm font-normal text-[var(--text-muted)]">· {rows.length}</span>
        </h2>
        {rows.length > 0 ? (
          <div className="relative w-full max-w-xs">
            <Search size={14} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-[var(--text-muted)]" aria-hidden />
            <Input type="search" aria-label={`Search ${title.toLowerCase()}`} value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search" className="py-1.5 pl-8 text-sm" />
          </div>
        ) : null}
      </div>
      <DataTable
        bare
        label={title}
        itemName="records"
        columns={tableColumns}
        rows={visible}
        rowKey={(row) => row.id}
        empty={<p className="text-center text-sm text-[var(--text-muted)]">{rows.length === 0 ? empty : "No records match your search."}</p>}
      />
    </Card>
  );
}
