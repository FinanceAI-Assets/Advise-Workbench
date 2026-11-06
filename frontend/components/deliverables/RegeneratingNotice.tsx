import { Loader2 } from "lucide-react";

/**
 * Banner shown while an artifact is being regenerated: what is rebuilt, and a progress bar that only says work
 * is under way (the backend reports no progress, so it shows no percentage).
 */
export function RegeneratingNotice({
  label,
  version,
  rebuildingSlides = [],
  totalSlides = 0,
}: {
  /** What is regenerated, for example "deck" or "document". */
  label: string;
  version: string;
  /** Slides rebuilt in a partial deck regeneration; empty when the whole artifact is rebuilt. */
  rebuildingSlides?: number[];
  totalSlides?: number;
}) {
  const partial = rebuildingSlides.length > 0 && rebuildingSlides.length < totalSlides;
  const kept = totalSlides - rebuildingSlides.length;
  return (
    <div role="status" aria-live="polite" className="overflow-hidden rounded-lg border border-[#CFE3B8] bg-[#F6FAF1]">
      <div className="flex items-start gap-3 p-4">
        <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-white text-[var(--accent-green-dark)] shadow-sm">
          <Loader2 size={18} className="animate-spin" aria-hidden />
        </span>
        <div className="min-w-0 space-y-1">
          <p className="text-sm font-semibold text-[var(--text-default)]">
            Regenerating the {label} as {version}
          </p>
          <p className="text-xs text-[var(--text-muted)]">
            {partial
              ? `Rebuilding slide${rebuildingSlides.length === 1 ? "" : "s"} ${rebuildingSlides.join(", ")}; the other ${kept} stay as they are.`
              : `Rebuilding the whole ${label} with your feedback.`}{" "}
            This usually takes a few minutes. You can leave this page; the new version loads here when it is ready.
          </p>
        </div>
      </div>
      <div className="h-1 w-full overflow-hidden bg-[#E3EFD6]" aria-hidden>
        <div className="h-full w-2/5 animate-indeterminate rounded-full bg-[var(--accent-green)]" />
      </div>
    </div>
  );
}

/** Veil over a slide that is being rebuilt, so its old content is not mistaken for the new one. */
export function RegeneratingSlideOverlay() {
  return (
    <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 rounded-lg bg-white/75 backdrop-blur-[2px]">
      <Loader2 size={24} className="animate-spin text-[var(--accent-green-dark)]" aria-hidden />
      <p className="text-sm font-semibold text-[var(--text-default)]">Rebuilding this slide…</p>
      <p className="text-xs text-[var(--text-muted)]">The new version appears here when it is ready.</p>
    </div>
  );
}
