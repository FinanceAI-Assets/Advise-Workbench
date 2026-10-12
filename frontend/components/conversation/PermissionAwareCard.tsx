import { ShieldCheck } from "lucide-react";

import { NoticeCard } from "@/components/ui/NoticeCard";

export function PermissionAwareCard() {
  return (
    <NoticeCard
      icon={<ShieldCheck size={18} aria-hidden />}
      title="Permission-aware retrieval"
      description="Only sources you can access are used. External web search is off. Source permissions travel with the draft."
    />
  );
}
