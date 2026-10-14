import type { ReactNode } from "react";

import { Card } from "@/components/ui/Card";
import { cn } from "@/lib/utils";

export type NoticeCardTone = "success" | "warning" | "error";

const TONE_CLASS: Record<NoticeCardTone, { card: string; icon: string; title: string; description: string }> = {
  success: {
    card: "border-[var(--surface-border)]",
    icon: "text-[var(--accent-green)]",
    title: "text-[var(--text-default)]",
    description: "text-[var(--text-muted)]",
  },
  warning: {
    card: "border-[#F3E2C0] bg-[#FCF3E2]",
    icon: "text-[#8C5B12]",
    title: "text-[#8C5B12]",
    description: "text-[#8C5B12]",
  },
  error: {
    card: "border-[#E8B4AE] bg-[#FBEFEB]",
    icon: "text-[#A53E37]",
    title: "text-[#A53E37]",
    description: "text-[#A53E37]",
  },
};

export function NoticeCard({
  tone = "success",
  icon,
  title,
  description,
  className,
}: {
  tone?: NoticeCardTone;
  icon: ReactNode;
  title: string;
  description: string;
  className?: string;
}) {
  const styles = TONE_CLASS[tone];
  return (
    <Card className={cn("flex items-start gap-2", styles.card, className)}>
      <span className={cn("mt-0.5 shrink-0", styles.icon)}>{icon}</span>
      <div>
        <p className={cn("text-sm font-semibold", styles.title)}>{title}</p>
        <p className={cn("text-xs", styles.description)}>{description}</p>
      </div>
    </Card>
  );
}
