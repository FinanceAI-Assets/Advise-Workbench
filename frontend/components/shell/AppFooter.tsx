/** Footer of every workbench and admin screen. The shells keep it at the bottom of the window on short pages. */
export function AppFooter() {
  return (
    <footer className="mt-6 flex flex-wrap items-center justify-between gap-2 border-t border-[var(--surface-border)] pt-4 text-xs text-[var(--text-muted)]">
      <span>Illustrative content only · No real client or confidential information</span>
      <span>Advise Workbench · Secure advisory environment</span>
    </footer>
  );
}
