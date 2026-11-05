"use client";

import { ArrowLeft } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";

const BACK_CLASS =
  "flex h-8 w-8 shrink-0 items-center justify-center rounded-md border border-[var(--surface-border)] bg-white !text-[var(--text-default)] !no-underline transition hover:bg-[var(--surface-muted)]";
const DEFAULT_HOME = "/engagements";

/**
 * Arrow-only back control. `href` goes to the screen's parent and `onClick` steps back within one
 * screen. With neither, for screens reachable from anywhere, it returns to the previous page, or
 * to the workspace home when the page opened with no history (a new tab or a shared link).
 */
export function BackButton({ href, onClick, label = "Go back" }: { href?: string; onClick?: () => void; label?: string }) {
  const router = useRouter();

  if (href) {
    return (
      <Link href={href} aria-label={label} title={label} className={BACK_CLASS}>
        <ArrowLeft size={16} aria-hidden />
      </Link>
    );
  }

  const goBack = () => {
    if (window.history.length > 1) router.back();
    else router.push(DEFAULT_HOME);
  };

  return (
    <button type="button" aria-label={label} title={label} onClick={onClick ?? goBack} className={BACK_CLASS}>
      <ArrowLeft size={16} aria-hidden />
    </button>
  );
}
