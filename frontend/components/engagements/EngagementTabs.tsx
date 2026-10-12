import { cn } from "@/lib/utils";

export type EngagementTabKey = "overview" | "sources" | "deliverables" | "team" | "activity";

type Tab<K extends string> = { key: K; label: string; count?: number };

export function EngagementTabs<K extends string>({
  tabs,
  active,
  onChange,
}: {
  tabs: Tab<K>[];
  active: K;
  onChange: (key: K) => void;
}) {
  return (
    <div className="flex gap-6 border-b border-[var(--surface-border)]" role="tablist">
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
              "border-b-2 pb-3 text-sm font-medium transition",
              isActive
                ? "border-[var(--accent-green)] text-[var(--text-default)]"
                : "border-transparent text-[var(--text-muted)] hover:text-[var(--text-default)]"
            )}
          >
            {tab.label}
            {typeof tab.count === "number" ? ` (${tab.count})` : ""}
          </button>
        );
      })}
    </div>
  );
}
