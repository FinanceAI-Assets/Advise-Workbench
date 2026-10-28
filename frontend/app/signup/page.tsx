"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";

import { AuthLayout } from "@/components/auth/AuthLayout";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { useAuth } from "@/lib/auth-context";

function SignupForm() {
  const { register, ready } = useAuth();
  const router = useRouter();
  const search = useSearchParams();
  const next = search.get("next") || "/engagements";
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (name.trim().length < 2) {
      setError("Enter your full name.");
      return;
    }
    if (password !== confirmPassword) {
      setError("Passwords do not match.");
      return;
    }
    setBusy(true);
    try {
      // The API provisions first-time users through the existing login contract.
      await register(email.trim(), password, name.trim());
      router.push(next);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to create your account.");
    } finally {
      setBusy(false);
    }
  }

  if (!ready) {
    return <p className="py-8 text-center text-sm text-[var(--text-muted)]">Loading…</p>;
  }

  return (
    <AuthLayout
      eyebrow="Get started"
      title="Create your account"
      description="Set up your secure workspace account and start turning insight into action."
      footer={
        <p className="text-sm text-[var(--text-muted)]">
          Already have an account?{" "}
          <Link href="/login" className="font-semibold text-[var(--accent-blue)] hover:underline">
            Sign in
          </Link>
        </p>
      }
    >
      <form onSubmit={onSubmit} className="mt-7 grid gap-4">
        <label className="grid gap-1.5 text-sm font-semibold text-[var(--text-default)]">
          Full name
          <Input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
            minLength={2}
            maxLength={255}
            placeholder="Your name"
            autoComplete="name"
          />
        </label>
        <p className="text-xs leading-5 text-[var(--text-muted)]">
          New accounts start as user accounts. Administrator access can only be granted by an existing administrator.
        </p>
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
            minLength={8}
            autoComplete="new-password"
          />
        </label>
        <label className="grid gap-1.5 text-sm font-semibold text-[var(--text-default)]">
          Confirm password
          <Input
            type="password"
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
            required
            minLength={8}
            autoComplete="new-password"
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
          {busy ? "Creating account…" : "Create account"}
        </Button>
        <p className="text-center text-xs leading-5 text-[var(--text-muted)]">
          Use your organization email address to request access.
        </p>
      </form>
    </AuthLayout>
  );
}

export default function SignupPage() {
  return (
    <Suspense fallback={<p className="py-12 text-center text-sm text-[var(--text-muted)]">Loading…</p>}>
      <SignupForm />
    </Suspense>
  );
}
