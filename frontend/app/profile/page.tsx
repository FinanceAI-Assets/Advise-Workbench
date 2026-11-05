"use client";

import { useEffect, useState } from "react";

import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Input } from "@/components/ui/Input";
import { ErrorNote, Field, PageFrame, PageSkeleton } from "@/components/workbench/PageFrame";
import { useUpdateProfileMutation } from "@/hooks/useWorkbench";
import { useAuth } from "@/lib/auth-context";

export default function ProfilePage() {
  const { user, setUser, logout } = useAuth();
  const save = useUpdateProfileMutation();
  const [name, setName] = useState("");
  const [title, setTitle] = useState("");

  useEffect(() => {
    if (!user) return;
    setName(user.name);
    setTitle(user.jobTitle);
  }, [user]);

  if (!user) return <PageSkeleton />;

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setUser(await save.mutateAsync({ full_name: name, job_title: title }));
  }

  return (
    <form onSubmit={(e) => void onSubmit(e)}>
      <PageFrame
        breadcrumb="User workspace / Side nav / Profile"
        title="Your profile"
        subtitle="Manage how your name appears in the workspace. Identity and access are governed by your organization."
        actions={
          <Button type="submit" disabled={save.isPending || name.trim().length < 2}>
            {save.isPending ? "Saving…" : "Save preferences"}
          </Button>
        }
      >
        <section className="grid gap-4 lg:grid-cols-[2fr_1fr]">
          <Card className="space-y-4">
            <h2 className="text-base font-semibold text-[var(--text-default)]">Preferences</h2>
            <label className="grid gap-1.5 text-2xs font-semibold uppercase tracking-wide text-[var(--text-muted)]">
              Display name
              <Input required minLength={2} maxLength={255} value={name} onChange={(e) => setName(e.target.value)} />
            </label>
            <label className="grid gap-1.5 text-2xs font-semibold uppercase tracking-wide text-[var(--text-muted)]">
              Role title
              <Input maxLength={128} value={title} onChange={(e) => setTitle(e.target.value)} placeholder="For example: Engagement lead" />
            </label>
            <ErrorNote error={save.error} />
            {save.isSuccess ? <p className="text-sm text-[#356B12]">Profile saved.</p> : null}
          </Card>
          <Card className="h-fit space-y-3">
            <h2 className="text-base font-semibold text-[var(--text-default)]">Account</h2>
            <Field label="Email">{user.email}</Field>
            <Field label="Workspace access">{user.isAdmin ? "Platform administrator" : "Workspace member"}</Field>
            <p className="text-xs text-[var(--text-muted)]">
              Engagement roles are set per engagement by its lead. Your email cannot be changed here.
            </p>
            <Button type="button" variant="secondary" onClick={logout}>
              Sign out
            </Button>
          </Card>
        </section>
      </PageFrame>
    </form>
  );
}
