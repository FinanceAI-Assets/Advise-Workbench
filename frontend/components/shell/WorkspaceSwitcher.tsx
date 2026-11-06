import { ShieldCheck } from "lucide-react";

/**
 * Names the admin workspace at the top of its side nav. It is a label, not a switch: moving between the admin and
 * user workspaces is the option at the foot of each nav, offered to administrators only. The user workspace shows no
 * label.
 */
export function WorkspaceLabel() {
  return (
    <div className="flex min-h-11 w-full items-center gap-2 rounded-md border border-[color:color-mix(in_srgb,var(--primary-700)_35%,transparent)] bg-[var(--primary-800)] px-3 py-2 text-sm font-semibold text-white">
      <ShieldCheck size={16} className="shrink-0 text-[var(--accent-green)]" aria-hidden />
      <span>Admin workspace</span>
    </div>
  );
}
