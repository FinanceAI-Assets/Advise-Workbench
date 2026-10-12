import type { SlideDetail } from "@/types/api";

export function SlideCanvas({ slide }: { slide: SlideDetail }) {
  return (
    <div className="space-y-4 rounded-lg border border-[var(--surface-border)] bg-white p-5">
      <div className="flex items-center justify-between">
        <p className="text-2xs font-semibold uppercase tracking-wide text-[var(--text-muted)]">{slide.breadcrumb}</p>
        <span className="h-2 w-2 rounded-full bg-[var(--accent-green)]" aria-hidden />
      </div>
      <h3 className="text-xl font-semibold text-[var(--text-default)]">{slide.headline}</h3>
      <div className="grid gap-4 sm:grid-cols-3">
        {slide.phases.map((phase) => (
          <div key={phase.label} className="space-y-1 rounded-md border-t-2 border-t-[var(--accent-green)] bg-[var(--surface-muted)] p-3">
            <p className="text-xs font-semibold text-[var(--accent-green-dark)]">{phase.label}</p>
            <p className="text-sm font-semibold text-[var(--text-default)]">{phase.title}</p>
            <p className="text-xs text-[var(--text-muted)]">{phase.description}</p>
          </div>
        ))}
      </div>
      <p className="text-xs text-[var(--text-muted)]">{slide.sources}</p>
      <div className="flex items-center justify-between border-t border-[var(--surface-border)] pt-3 text-xs text-[var(--text-muted)]">
        <span>{slide.footerMeta}</span>
        <span>{slide.pageLabel}</span>
      </div>
    </div>
  );
}
