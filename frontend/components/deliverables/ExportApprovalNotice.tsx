import { AlertTriangle } from "lucide-react";

import { cn } from "@/lib/utils";

/** Amber notice that exports stay locked until the independent review approves them. */
export function ExportApprovalNotice({
  title = "Export requires approval",
  description,
  className,
}: {
  title?: string;
  description: string;
  className?: string;
}) {
  return (
    <div className={cn("flex items-start gap-2 rounded-lg border border-[#F3E2C0] bg-[#FCF3E2] p-3", className)}>
      <AlertTriangle size={16} className="mt-0.5 shrink-0 text-[#8C5B12]" aria-hidden />
      <div>
        <p className="text-sm font-semibold text-[#8C5B12]">{title}</p>
        <p className="text-xs text-[#8C5B12]">{description}</p>
      </div>
    </div>
  );
}
