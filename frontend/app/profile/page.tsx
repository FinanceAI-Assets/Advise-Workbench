"use client";

import { useEffect, useState } from "react";

import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Select } from "@/components/ui/Select";
import { ErrorNote, Field, PageFrame, PageSkeleton } from "@/components/workbench/PageFrame";
import { useEngagementsQuery } from "@/hooks/useEngagements";
import { useUpdateProfileMutation } from "@/hooks/useWorkbench";
import { useAuth } from "@/lib/auth-context";

function PreferenceRow({
  title,
  description,
  enabled,
  onChange,
}: {
  title: string;
  description: string;
  enabled: boolean;
  onChange: (value: boolean) => void;
}) {
  return (
    <div className="flex items-start justify-between gap-4 py-2">
      <div className="min-w-0">
        <p className="text-sm font-semibold text-[var(--text-default)]">{title}</p>
        <p className="mt-0.5 text-xs text-[var(--text-muted)]">{description}</p>
      </div>
      <button
        type="button"
        role="switch"
        aria-checked={enabled}
        onClick={() => onChange(!enabled)}
        className="shrink-0 text-xs font-medium text-[var(--accent-green-dark)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--accent-blue)]"
      >
        {enabled ? "On" : "Off"}
      </button>
    </div>
  );
}

export default function ProfilePage() {
  const { user, setUser } = useAuth();
  const save = useUpdateProfileMutation();
  const engagements = useEngagementsQuery(
    { q: "", status: "active", mine: false, page: 1 },
    Boolean(user)
  );
  const [name, setName] = useState("");
  const [title, setTitle] = useState("");
  const [timeZone, setTimeZone] = useState("Europe / London");
  const [language, setLanguage] = useState("English (UK)");
  const [workspace, setWorkspace] = useState("User workspace");
  const [assignments, setAssignments] = useState(true);
  const [updates, setUpdates] = useState(true);
  const [digest, setDigest] = useState(false);
  const [noise, setNoise] = useState(true);

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
        subtitle="Manage your workspace preferences. Identity and access are governed by your organization."
        actions={
          <Button type="submit" disabled={save.isPending || name.trim().length < 2}>
            {save.isPending ? "Saving…" : "Save preferences"}
          </Button>
        }
      >
        <section className="grid gap-4 lg:grid-cols-[285px_minmax(0,1fr)]">
          <Card className="h-fit space-y-5 p-4">
            <div className="flex items-center gap-2">
              <span className="text-base font-medium text-[var(--text-default)]">{user.name}</span>
              {user.isAdmin ? (
                <span className="text-xs text-[var(--text-muted)]">· Admin</span>
              ) : null}
            </div>
            <div className="grid gap-4">
              <Field label="Role">{title || "Engagement lead"}</Field>
              <Field label="Practice">Advisory / Transformation</Field>
              <Field label="Identity">{user.email}</Field>
              <Field label="Sign-in">Organization SSO · MFA verified</Field>
            </div>
            <div className="rounded-md bg-[var(--primary-50)] p-3">
              <p className="text-xs font-semibold text-[var(--text-default)]">Identity managed centrally</p>
              <p className="mt-1 text-xs leading-5 text-[var(--text-muted)]">
                Name, email and role changes must be requested through your administrator.
              </p>
            </div>
          </Card>

          <Card className="space-y-3 p-4 sm:p-5">
            <h2 className="text-base font-medium text-[var(--text-default)]">Preferences</h2>
            <div className="grid gap-3 sm:grid-cols-2">
              <label className="grid gap-1.5 text-2xs font-semibold uppercase tracking-wide text-[var(--text-muted)]">
                Time zone
                <Select value={timeZone} onChange={(e) => setTimeZone(e.target.value)} aria-label="Time zone">
                  <option>Europe / London</option>
                  <option>Asia / Kolkata</option>
                  <option>America / New York</option>
                </Select>
              </label>
              <label className="grid gap-1.5 text-2xs font-semibold uppercase tracking-wide text-[var(--text-muted)]">
                Language
                <Select value={language} onChange={(e) => setLanguage(e.target.value)} aria-label="Language">
                  <option>English (UK)</option>
                  <option>English (US)</option>
                </Select>
              </label>
            </div>
            <label className="grid gap-1.5 text-2xs font-semibold uppercase tracking-wide text-[var(--text-muted)]">
              Default workspace
              <Select value={workspace} onChange={(e) => setWorkspace(e.target.value)} aria-label="Default workspace">
                <option>User workspace</option>
                <option>Advisory / Transformation</option>
              </Select>
            </label>
            <div className="divide-y divide-[var(--surface-border)] pt-1">
              <PreferenceRow
                title="Review assignments & mentions"
                description="In-app notifications and email"
                enabled={assignments}
                onChange={setAssignments}
              />
              <PreferenceRow
                title="Artifact generation updates"
                description="In-app notifications"
                enabled={updates}
                onChange={setUpdates}
              />
              <PreferenceRow
                title="Weekly workspace digest"
                description="Email · Monday, 09:00"
                enabled={digest}
                onChange={setDigest}
              />
              <PreferenceRow
                title="Reduced notification noise"
                description="Combine repeated ingestion updates"
                enabled={noise}
                onChange={setNoise}
              />
            </div>
            <div className="border-t border-[var(--surface-border)] pt-3">
              <Field label="Session">Last sign-in · Today · Managed device</Field>
            </div>
          </Card>
        </section>

        <ErrorNote error={save.error} />
        {save.isSuccess ? <p className="text-sm text-[#356B12]">Profile preferences saved.</p> : null}

        <section className="deloitte-surface overflow-hidden">
          <div className="border-b border-[var(--surface-border)] px-4 py-4">
            <h2 className="text-base font-medium text-[var(--text-default)]">Your engagement access</h2>
          </div>
          {engagements.isPending ? (
            <div className="px-4 py-5 text-sm text-[var(--text-muted)]">Loading engagements…</div>
          ) : engagements.data?.items.length ? (
            <div className="divide-y divide-[var(--surface-border)]">
              {engagements.data.items.map((engagement) => (
                <div key={engagement.id} className="px-4 py-3">
                  <p className="text-sm font-semibold text-[var(--text-default)]">
                    {engagement.name} · {engagement.code}
                  </p>
                  <p className="mt-1 text-xs text-[var(--text-muted)]">
                    Lead · {engagement.type} · {engagement.stage}
                  </p>
                </div>
              ))}
            </div>
          ) : (
            <div className="px-4 py-5 text-sm text-[var(--text-muted)]">
              No active engagements are assigned to you.
            </div>
          )}
        </section>
      </PageFrame>
    </form>
  );
}
