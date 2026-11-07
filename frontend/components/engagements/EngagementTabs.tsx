import { cn } from "@/lib/utils";

export type EngagementTabKey = "overview" | "sources" | "deliverables" | "team" | "activity";

type Tab<K extends string> = { key: K; label: string; count?: number };

export function EngagementTabs<K extends string>({
  tabs,
  active,
  onChange,
  large = false,
}: {
  tabs: Tab<K>[];
  active: K;
  onChange: (key: K) => void;
  /** Taller tabs that share the full width of the page. Narrow panels keep the compact default. */
  large?: boolean;
}) {
  return (
    <div
      className={cn(
        "max-w-full flex-wrap gap-1 rounded-lg border border-[var(--surface-border)] bg-white p-1 shadow-sm",
        large ? "flex w-full" : "inline-flex"
      )}
      role="tablist"
    >
      {tabs.map((tab) => {
        const isActive = tab.key === active;
        return (
          <button
            key={tab.key}
            type="button"
            role="tab"
            aria-selected={isActive}
            onClick={() => onChange(tab.key)}
            className={cn(
              "flex shrink-0 items-center gap-2 rounded-md transition",
              large ? "flex-1 justify-center px-2 py-3 text-base sm:px-6" : "px-4 py-2 text-sm",
              isActive
                ? "bg-[var(--accent-green)] font-semibold text-white shadow-sm"
                : "font-medium text-[var(--text-muted)] hover:bg-[var(--surface-muted)] hover:text-[var(--text-default)]"
            )}
          >
            {tab.label}
            {typeof tab.count === "number" ? (
              <span
                className={cn(
                  "min-w-5 rounded-full px-1.5 py-0.5 text-center text-2xs font-semibold leading-none",
                  isActive ? "bg-white/25 text-white" : "bg-[var(--surface-border)] text-[var(--text-muted)]"
                )}
              >
                {tab.count}
              </span>
            ) : null}
          </button>
        );
      })}
    </div>
  );
}
