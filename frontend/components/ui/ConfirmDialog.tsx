"use client";

import { type ReactNode, useEffect, useId } from "react";

import { Button } from "@/components/ui/Button";

/** A modal asking to confirm one action, with optional extra fields. Escape or Cancel closes it without acting. */
export function ConfirmDialog({
  title,
  description,
  confirmLabel,
  onConfirm,
  onCancel,
  busy = false,
  children,
}: {
  title: string;
  description: string;
  confirmLabel: string;
  onConfirm: () => void;
  onCancel: () => void;
  /** The confirmed action is in progress: both buttons wait for it. */
  busy?: boolean;
  children?: ReactNode;
}) {
  const titleId = useId();
  const descriptionId = useId();

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onCancel();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onCancel]);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" role="presentation">
      <div
        role="alertdialog"
        aria-modal="true"
        aria-labelledby={titleId}
        aria-describedby={descriptionId}
        className="w-full max-w-md space-y-4 rounded-lg bg-white p-6 shadow-2xl"
      >
        <div className="space-y-1">
          <h2 id={titleId} className="text-lg font-semibold text-[var(--text-default)]">
            {title}
          </h2>
          <p id={descriptionId} className="text-sm text-[var(--text-muted)]">
            {description}
          </p>
        </div>
        {children}
        <div className="flex justify-end gap-2">
          <Button type="button" variant="secondary" disabled={busy} onClick={onCancel}>
            Cancel
          </Button>
          <Button type="button" autoFocus disabled={busy} onClick={onConfirm}>
            {busy ? "Working…" : confirmLabel}
          </Button>
        </div>
      </div>
    </div>
  );
}
