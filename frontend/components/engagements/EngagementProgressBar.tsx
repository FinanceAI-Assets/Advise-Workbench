export function EngagementProgressBar({ value }: { value: number }) {
  return (
    <div className="flex items-center gap-2">
      <div className="h-2 w-28 rounded-full bg-[#DDE2DA]" aria-hidden>
        <div
          className="h-full rounded-full bg-[#356B12]"
          style={{ width: `${Math.min(100, Math.max(0, value))}%` }}
        />
      </div>
      <span className="w-10 shrink-0 text-right text-xs text-[var(--text-muted)]">{value}%</span>
    </div>
  );
}
