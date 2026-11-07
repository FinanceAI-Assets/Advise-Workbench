import { type TextareaHTMLAttributes } from "react";

import { cn } from "@/lib/utils";

export function Textarea(props: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return (
    <textarea
      {...props}
      className={cn(
        "w-full border border-[#E5E5E5] bg-white px-4 py-2 text-sm text-[var(--text-default)] outline-none ring-[var(--accent-green)] transition focus:ring-2 focus:border-[var(--accent-green)] resize-none",
        props.className
      )}
    />
  );
}
