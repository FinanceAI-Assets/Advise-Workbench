"use client";

import Link from "next/link";
import type { ReactNode } from "react";

import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { cn } from "@/lib/utils";

export const SKILLS_HOME = "/admin/console/skills";

/** White panel with a small title, as used by every skill management screen. */
export function Panel({ title, aside, children, className }: { title?: string; aside?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <Card className={cn("space-y-4 p-5", className)}>
      {title ? (
        <div className="flex items-center justify-between gap-3">
          <h2 className="text-sm font-medium text-[var(--text-default)]">{title}</h2>
          {aside}
        </div>
      ) : null}
      {children}
    </Card>
  );
}

export type RecordRow = {
  key: string;
  title: string;
  meta: Array<string | null | undefined>;
  /** Shown in green: the selected row, or the row the list leads with. */
  highlight?: boolean;
  onSelect?: () => void;
  extra?: ReactNode;
};

/** Bordered list whose header names the columns ("Skill / Version / Owner / Output") and whose rows carry them as meta. */
export function RecordList({ columns, rows, label }: { columns: string[]; rows: RecordRow[]; label: string }) {
  return (
    <div className="rounded-md border border-[var(--surface-border)]">
      <p className="px-3 pt-3 text-2xs font-medium text-[var(--text-muted)]">{columns.join(" / ")}</p>
      <ul aria-label={label} className="px-3 pb-2">
        {rows.map((row) => {
          const body = (
            <>
              <span className={cn("block text-xs font-semibold", row.highlight ? "text-[var(--accent-green-dark)]" : "text-[var(--text-default)]")}>
                {row.title}
              </span>
              <span className="mt-0.5 block text-2xs text-[var(--text-muted)]">{row.meta.filter(Boolean).join("   ·   ")}</span>
            </>
          );
          return (
            <li key={row.key} className="py-2">
              {row.onSelect ? (
                <Button
                  type="button"
                  variant="ghost"
                  aria-current={row.highlight ? "true" : undefined}
                  onClick={row.onSelect}
                  className="block w-full rounded-sm px-0 py-0 text-left font-normal hover:bg-transparent hover:underline"
                >
                  {body}
                </Button>
              ) : (
                body
              )}
              {row.extra}
            </li>
          );
        })}
      </ul>
    </div>
  );
}

/** A labelled box: the form fields on "Define a new skill" and the schema rows on Inputs & outputs. */
export function FieldBox({ label, required, children, className }: { label: string; required?: boolean; children: ReactNode; className?: string }) {
  return (
    <div
      className={cn(
        "rounded-md border border-[var(--surface-border)] bg-white px-3 py-2 focus-within:border-[var(--coral-black)]",
        className
      )}
    >
      <span className="block text-2xs font-medium uppercase tracking-wide text-[var(--text-muted)]">
        {label}
        {required ? " *" : ""}
      </span>
      <div className="mt-0.5 text-xs text-[var(--text-default)]">{children}</div>
    </div>
  );
}

/** Label above a value inside a panel. */
export function Fact({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div>
      <p className="text-2xs font-medium uppercase tracking-wide text-[var(--text-muted)]">{label}</p>
      <div className="mt-0.5 text-xs text-[var(--text-default)]">{children}</div>
    </div>
  );
}

const NOTE_TONE = {
  success: "bg-[#EFF6E6] text-[var(--text-default)]",
  warning: "bg-[#FCF3E2] text-[#8C5B12]",
  muted: "bg-[var(--surface-muted)] text-[var(--text-default)]",
};

/** Tinted note: green for a completed step, amber for a blocker, grey for policy context. */
export function Note({ tone = "muted", title, children, className }: { tone?: keyof typeof NOTE_TONE; title: string; children?: ReactNode; className?: string }) {
  return (
    <div className={cn("rounded-md px-3 py-2.5", NOTE_TONE[tone], className)} role={tone === "warning" ? "alert" : undefined}>
      <p className="text-xs font-semibold">{title}</p>
      {children ? <div className="mt-0.5 text-2xs opacity-80">{children}</div> : null}
    </div>
  );
}

export type SkillTabKey = "definition" | "inputs-outputs" | "permissions" | "history";

export const SKILL_TABS: Array<{ key: SkillTabKey; label: string; path: string }> = [
  { key: "definition", label: "Definition", path: "" },
  { key: "inputs-outputs", label: "Inputs & outputs", path: "/inputs-outputs" },
  { key: "permissions", label: "Permissions", path: "/permissions" },
  { key: "history", label: "History", path: "/history" },
];

/** Underlined tab links shared by a skill's pages. */
export function TabLinks({ tabs, active }: { tabs: Array<{ key: string; label: string; href: string }>; active?: string }) {
  return (
    <nav className="flex gap-6 border-b border-[var(--surface-border)]" aria-label="Sections">
      {tabs.map((tab) => (
        <Link
          key={tab.key}
          href={tab.href}
          aria-current={tab.key === active ? "page" : undefined}
          className={cn(
            "-mb-px border-b-2 pb-2 text-xs !no-underline transition",
            tab.key === active
              ? "border-[var(--accent-green)] font-medium !text-[var(--accent-green-dark)]"
              : "border-transparent !text-[var(--text-muted)] hover:!text-[var(--text-default)]"
          )}
        >
          {tab.label}
        </Link>
      ))}
    </nav>
  );
}

export function SkillTabs({ skillId, active }: { skillId: string; active?: SkillTabKey }) {
  return <TabLinks active={active} tabs={SKILL_TABS.map((t) => ({ key: t.key, label: t.label, href: `${SKILLS_HOME}/${skillId}${t.path}` }))} />;
}

/**
 * Classes for an Input / Textarea / Select placed inside a FieldBox: no border, padding or focus outline of its own,
 * since the box shows focus instead.
 */
export const BARE_CONTROL = "border-0 bg-transparent px-0 py-0.5 text-xs focus:ring-0 focus-visible:outline-none";
export const BARE_SELECT = "min-h-0 border-0 bg-transparent p-0 text-xs focus:ring-0 focus-visible:outline-none";

/** Green primary and white secondary buttons at the console's compact size. */
export const BUTTON_COMPACT = "px-4 py-2 text-xs font-semibold whitespace-nowrap";
export const BUTTON_SECONDARY = `${BUTTON_COMPACT} border border-[var(--surface-border-strong)]`;
