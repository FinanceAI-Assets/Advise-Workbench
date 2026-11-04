import { type ReactNode } from "react";

import { BrandMark } from "@/components/shell/BrandMark";

type AuthLayoutProps = {
  eyebrow: string;
  title: string;
  description: string;
  children: ReactNode;
  footer: ReactNode;
};

export function AuthLayout({
  eyebrow,
  title,
  description,
  children,
  footer,
}: AuthLayoutProps) {
  return (
    <main className="min-h-screen bg-[var(--primary-50)] px-4 py-8 sm:px-6 sm:py-12">
      <div className="mx-auto grid min-h-[calc(100vh-4rem)] w-full max-w-5xl items-center gap-8 lg:grid-cols-[minmax(0,1fr)_420px] lg:gap-16">
        <section className="hidden lg:block">
          <BrandMark />
          <p className="mt-16 max-w-lg text-4xl font-semibold leading-tight tracking-[-0.03em] text-[var(--text-default)]">
            Turn complex work into clear, confident decisions.
          </p>
          <p className="mt-5 max-w-md text-base leading-7 text-[var(--text-muted)]">
            A focused workspace for creating evidence-led advice, managing engagements, and
            delivering work your teams can trust.
          </p>
          <div className="mt-10 flex items-center gap-3 text-sm text-[var(--text-muted)]">
            <span className="h-2 w-2 rounded-full bg-[var(--accent-green)]" aria-hidden />
            Secure workspace access
          </div>
        </section>

        <section className="w-full">
          <div className="mb-8 flex justify-center lg:hidden">
            <BrandMark />
          </div>
          <div className="deloitte-surface p-6 sm:p-8">
            <p className="text-2xs font-semibold uppercase tracking-[0.14em] text-[var(--accent-blue)]">
              {eyebrow}
            </p>
            <h1 className="mt-3 text-2xl font-semibold tracking-[-0.02em] text-[var(--text-default)]">
              {title}
            </h1>
            <p className="mt-2 text-sm leading-6 text-[var(--text-muted)]">{description}</p>
            {children}
          </div>
          <div className="mt-5 text-center">{footer}</div>
        </section>
      </div>
    </main>
  );
}
