"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";

import { AuthLayout } from "@/components/auth/AuthLayout";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { getApiBase } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";

function LoginForm() {
  const { login, loginWithMicrosoftCode, ready } = useAuth();
  const router = useRouter();
  const search = useSearchParams();
  const next = search.get("next") || "/engagements";
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [microsoftBusy, setMicrosoftBusy] = useState(false);
  const [microsoftError, setMicrosoftError] = useState<string | null>(null);

  const microsoftCode = search.get("microsoft_code");
  const microsoftErrorFromRedirect = search.get("microsoft_error");

  useEffect(() => {
    if (!ready || !microsoftCode) return;
    let cancelled = false;
    setMicrosoftBusy(true);
    void loginWithMicrosoftCode(microsoftCode)
      .then((redirectPath) => {
        if (!cancelled) router.replace(redirectPath);
      })
      .catch((err) => {
        if (!cancelled) {
          setMicrosoftError(
            err instanceof Error ? err.message : "Unable to complete Microsoft sign-in."
          );
        }
      })
      .finally(() => {
        if (!cancelled) setMicrosoftBusy(false);
      });
    return () => {
      cancelled = true;
    };
  }, [loginWithMicrosoftCode, microsoftCode, ready, router]);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await login(email.trim(), password);
      router.push(next);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to sign in. Please try again.");
    } finally {
      setBusy(false);
    }
  }

  if (!ready) {
    return <p className="py-8 text-center text-sm text-[var(--text-muted)]">Loading…</p>;
  }

  return (
    <AuthLayout
      eyebrow="Advise Workbench"
      title="Welcome back"
      description="Sign in with your organization account to continue to your workspace."
      footer={
        <p className="text-sm text-[var(--text-muted)]">
          New to Advise Workbench?{" "}
          <Link href="/signup" className="font-semibold text-[var(--accent-blue)] hover:underline">
            Create an account
          </Link>
        </p>
      }
    >
      <form onSubmit={onSubmit} className="mt-7 grid gap-5">
        <label className="grid gap-1.5 text-sm font-semibold text-[var(--text-default)]">
          Work email
          <Input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            placeholder="name@deloitte.com"
            autoComplete="email"
          />
        </label>
        <label className="grid gap-1.5 text-sm font-semibold text-[var(--text-default)]">
          Password
          <Input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            autoComplete="current-password"
          />
        </label>
        {error ? (
          <p
            role="alert"
            className="rounded-md border border-[color:color-mix(in_srgb,var(--error)_35%,white)] bg-[var(--error-light)] px-3 py-2 text-sm text-[var(--error)]"
          >
            {error}
          </p>
        ) : null}
        <Button type="submit" disabled={busy} className="mt-1 w-full justify-center py-2.5">
          {busy ? "Signing in…" : "Sign in"}
        </Button>
      </form>
      <div className="my-6 flex items-center gap-3 text-xs text-[var(--text-muted)]">
        <span className="h-px flex-1 bg-[var(--surface-border)]" />
        <span>or</span>
        <span className="h-px flex-1 bg-[var(--surface-border)]" />
      </div>
      <a
        href={`${getApiBase()}/api/auth/microsoft/start?${new URLSearchParams({ next })}`}
        aria-disabled={microsoftBusy}
        className="flex w-full items-center justify-center gap-3 rounded-md border-2 border-[var(--coral-black)] bg-white px-4 py-2.5 text-sm font-medium text-[var(--coral-black)] transition hover:bg-[var(--primary-50)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--coral-black)] aria-disabled:pointer-events-none aria-disabled:opacity-60"
      >
        <span className="grid h-4 w-4 grid-cols-2 grid-rows-2 gap-px" aria-hidden>
          <span className="bg-[#f35325]" />
          <span className="bg-[#81bc06]" />
          <span className="bg-[#05a6f0]" />
          <span className="bg-[#ffba08]" />
        </span>
        {microsoftBusy ? "Signing in with Microsoft…" : "Continue with Microsoft"}
      </a>
      {microsoftError || microsoftErrorFromRedirect ? (
        <p
          role="alert"
          className="mt-4 rounded-md border border-[color:color-mix(in_srgb,var(--error)_35%,white)] bg-[var(--error-light)] px-3 py-2 text-sm text-[var(--error)]"
        >
          {microsoftError || microsoftErrorFromRedirect}
        </p>
      ) : null}
    </AuthLayout>
  );
}

export default function LoginPage() {
  return (
    <Suspense fallback={<p className="py-12 text-center text-sm text-[var(--text-muted)]">Loading…</p>}>
      <LoginForm />
    </Suspense>
  );
}
