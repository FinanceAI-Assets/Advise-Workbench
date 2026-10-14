"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Input } from "@/components/ui/Input";
import { Select } from "@/components/ui/Select";
import { Textarea } from "@/components/ui/Textarea";
import { ErrorNote, Field, PageFrame } from "@/components/workbench/PageFrame";
import { useCreateEngagementMutation } from "@/hooks/useEngagements";

const CLASSIFICATIONS = ["Internal · Engagement-scoped", "Restricted · Engagement-scoped"];
const MIN_BRIEF = 30;

function Labeled({ label, hint, children }: { label: string; hint?: string; children: React.ReactNode }) {
  return (
    <label className="grid gap-1.5 text-2xs font-semibold uppercase tracking-wide text-[var(--text-muted)]">
      {label}
      {children}
      {hint ? <span className="text-xs font-normal normal-case tracking-normal">{hint}</span> : null}
    </label>
  );
}

export default function NewEngagementPage() {
  const router = useRouter();
  const create = useCreateEngagementMutation();
  const [name, setName] = useState("");
  const [clientOrg, setClientOrg] = useState("");
  const [brief, setBrief] = useState("");
  const [startDate, setStartDate] = useState("");
  const [targetClose, setTargetClose] = useState("");
  const [classification, setClassification] = useState(CLASSIFICATIONS[0]);

  const datesValid = !startDate || !targetClose || startDate <= targetClose;
  const complete = name.trim().length >= 3 && clientOrg.trim().length > 0 && brief.trim().length >= MIN_BRIEF && datesValid;

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!complete) return;
    const created = await create.mutateAsync({
      name: name.trim(),
      clientOrg: clientOrg.trim(),
      brief: brief.trim(),
      startDate: startDate || undefined,
      targetClose: targetClose || undefined,
      classification,
    });
    router.push(`/engagements/${created.id}`);
  }

  return (
    <form onSubmit={(e) => void onSubmit(e)}>
      <PageFrame
        breadcrumb={
          <>
            User workspace / <Link href="/engagements">Engagements</Link> / New engagement
          </>
        }
        title="Create an engagement"
        subtitle="Set a grounded brief and access boundary before starting an advisory conversation."
        actions={
          <>
            <Link href="/engagements">
              <Button type="button" variant="secondary">
                Cancel
              </Button>
            </Link>
            <Button type="submit" disabled={!complete || create.isPending}>
              {create.isPending ? "Creating…" : "Create engagement"}
            </Button>
          </>
        }
      >
        <section className="grid gap-4 lg:grid-cols-[2fr_1fr]">
          <Card className="space-y-4">
            <h2 className="text-base font-semibold text-[var(--text-default)]">Engagement details</h2>
            <div className="grid gap-4 md:grid-cols-2">
              <Labeled label="Engagement name *" hint="Use a descriptive name; the engagement ID is assigned on creation.">
                <Input value={name} onChange={(e) => setName(e.target.value)} required minLength={3} maxLength={255} />
              </Labeled>
              <Labeled label="Client / sample organization *">
                <Input value={clientOrg} onChange={(e) => setClientOrg(e.target.value)} required maxLength={255} />
              </Labeled>
            </div>
            <Labeled
              label="Brief *"
              hint={`Required · At least ${MIN_BRIEF} characters. Distinguish objectives from unvalidated assumptions.`}
            >
              <Textarea value={brief} onChange={(e) => setBrief(e.target.value)} required minLength={MIN_BRIEF} rows={4} />
            </Labeled>
            <div className="grid gap-4 md:grid-cols-2">
              <Labeled label="Start date">
                <Input type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} />
              </Labeled>
              <Labeled label="Target close" hint={datesValid ? undefined : "Target close must be on or after the start date."}>
                <Input type="date" value={targetClose} onChange={(e) => setTargetClose(e.target.value)} />
              </Labeled>
            </div>
            <Labeled label="Security classification *">
              <Select value={classification} onChange={(e) => setClassification(e.target.value)}>
                {CLASSIFICATIONS.map((option) => (
                  <option key={option}>{option}</option>
                ))}
              </Select>
            </Labeled>
            <ErrorNote error={create.error} />
            <p
              className={
                complete
                  ? "rounded-md bg-[#EFF6E6] px-3 py-2 text-sm text-[#356B12]"
                  : "rounded-md bg-[var(--surface-muted)] px-3 py-2 text-sm text-[var(--text-muted)]"
              }
            >
              {complete
                ? "Ready to create. Required fields are complete."
                : "Complete the name, organization and brief to create the engagement."}
            </p>
          </Card>

          <Card className="h-fit space-y-4">
            <h2 className="text-base font-semibold text-[var(--text-default)]">Creation summary</h2>
            <Field label="Access group">You become the engagement lead. Add the team from Manage access.</Field>
            <Field label="Retention">180 days after close</Field>
            <Field label="What happens next">
              Brief → Sources → Draft → Review → Export. Your new engagement opens in Brief. Attach permitted documents
              before running a skill.
            </Field>
            <p className="rounded-md border border-[#F3E2C0] bg-[#FCF3E2] px-3 py-2 text-xs text-[#8C5B12]">
              <span className="block font-semibold">No real client information</span>
              This sample workspace contains fictional organizations and illustrative content only.
            </p>
          </Card>
        </section>
      </PageFrame>
    </form>
  );
}
