"use client";

import Link from "next/link";
import { useState } from "react";

import { DocumentUploader } from "@/components/documents/DocumentUploader";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { Input } from "@/components/ui/Input";
import { Select } from "@/components/ui/Select";
import { Skeleton } from "@/components/ui/Skeleton";
import { Textarea } from "@/components/ui/Textarea";
import { ErrorNote, Field } from "@/components/workbench/PageFrame";
import {
  MEMBER_ROLES,
  useEngagementActivityQuery,
  useExportReadinessQuery,
  useMemberMutation,
  useUpdateEngagementMutation,
} from "@/hooks/useEngagements";
import { useAuth } from "@/lib/auth-context";
import { downloadFile } from "@/lib/workbenchApi";
import type { EngagementDetail } from "@/types/api";

// Bodies of the engagement detail tabs and workflow steps that are not the Overview.

type SectionProps = { id: string; detail: EngagementDetail };

export function SourcesSection({ id, detail }: SectionProps) {
  const practices = detail.practices ?? [];
  return (
    <section className="grid gap-4 lg:grid-cols-[2fr_1fr]">
      <Card className="space-y-3">
        <h2 className="text-base font-semibold text-[var(--text-default)]">Engagement documents</h2>
        <p className="text-xs text-[var(--text-muted)]">
          Uploaded files are indexed for this engagement only. Supported: txt, md, csv, json, pdf, docx, pptx, xlsx.
        </p>
        <DocumentUploader projectId={id} />
      </Card>
      <Card className="h-fit space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-base font-semibold text-[var(--text-default)]">Approved library practices</h2>
          <span className="text-xs text-[var(--text-muted)]">{practices.length} in scope</span>
        </div>
        {practices.length === 0 ? (
          <p className="text-sm text-[var(--text-muted)]">No practices added yet.</p>
        ) : (
          <ul className="space-y-2 text-sm">
            {practices.map((practice) => (
              <li key={practice.id}>
                <Link href={`/library?practice=${encodeURIComponent(practice.practiceId)}`}>{practice.title}</Link>
              </li>
            ))}
          </ul>
        )}
        <Link href="/library" className="!no-underline">
          <Button variant="secondary" className="w-full justify-center">
            Browse the library
          </Button>
        </Link>
        <p className="text-xs text-[var(--text-muted)]">
          Only permitted, indexed sources are retrieved. Source boundaries travel with drafts.
        </p>
      </Card>
    </section>
  );
}

export function TeamSection({ id, detail }: SectionProps) {
  const { user } = useAuth();
  const members = detail.teamMembers;
  const change = useMemberMutation(id);
  const [selectedId, setSelectedId] = useState(members[0]?.id ?? "");
  const [email, setEmail] = useState("");
  const [role, setRole] = useState("Contributor");
  const selected = members.find((m) => m.id === selectedId) ?? members[0];
  const isLead = members.some((m) => m.userId === user?.id && m.role === "Engagement lead");

  async function invite(e: React.FormEvent) {
    e.preventDefault();
    await change.mutateAsync({ action: "add", email: email.trim(), role });
    setEmail("");
  }

  return (
    <section className="grid gap-4 lg:grid-cols-[2fr_1fr]">
      <Card className="space-y-3">
        <h2 className="text-base font-semibold text-[var(--text-default)]">Engagement members</h2>
        <table className="w-full text-left text-sm">
          <thead className="text-xs text-[var(--text-muted)]">
            <tr>
              <th className="py-2 font-medium">Member</th>
              <th className="py-2 font-medium">Role</th>
              <th className="py-2 font-medium">Permission</th>
              <th className="py-2 font-medium">Status</th>
            </tr>
          </thead>
          <tbody>
            {members.map((member) => (
              <tr
                key={member.id}
                onClick={() => setSelectedId(member.id)}
                className={`cursor-pointer border-t border-[var(--surface-border)] ${
                  member.id === selected?.id ? "bg-[#EFF6E6]" : ""
                }`}
              >
                <td className="py-3 font-medium text-[var(--text-default)]">{member.name}</td>
                <td className="py-3">
                  {isLead ? (
                    <Select
                      aria-label={`Role for ${member.name}`}
                      value={member.role}
                      onClick={(e) => e.stopPropagation()}
                      onChange={(e) => change.mutate({ action: "role", memberId: member.id, role: e.target.value })}
                      className="w-auto"
                    >
                      {MEMBER_ROLES.map((option) => (
                        <option key={option}>{option}</option>
                      ))}
                    </Select>
                  ) : (
                    member.role
                  )}
                </td>
                <td className="py-3 text-[var(--text-muted)]">{member.permission}</td>
                <td className="py-3 text-[var(--text-muted)]">{member.status}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <ErrorNote error={change.error} />
        <p className="rounded-md bg-[var(--surface-muted)] px-3 py-2 text-xs text-[var(--text-muted)]">
          <span className="block font-semibold text-[var(--text-default)]">Least-privilege collaboration</span>
          All members can see only permitted engagement content. Library and restricted-source rights are evaluated
          separately.
        </p>
      </Card>

      <div className="space-y-4">
        {selected ? (
          <Card className="space-y-3">
            <h2 className="text-base font-semibold text-[var(--text-default)]">Selected team member</h2>
            <Field label="Member">{selected.name}</Field>
            <Field label="Email">{selected.email}</Field>
            <Field label="Role">{selected.role}</Field>
            <Field label="Permission">{selected.permission}</Field>
            {isLead && selected.userId !== user?.id ? (
              <Button
                variant="secondary"
                disabled={change.isPending}
                onClick={() => change.mutate({ action: "remove", memberId: selected.id })}
              >
                Remove from engagement
              </Button>
            ) : null}
          </Card>
        ) : null}
        {isLead ? (
          <Card id="manage-access">
            <form onSubmit={(e) => void invite(e)} className="space-y-3">
              <h2 className="text-base font-semibold text-[var(--text-default)]">Manage engagement access</h2>
              <label className="grid gap-1.5 text-2xs font-semibold uppercase tracking-wide text-[var(--text-muted)]">
                Invite organization member
                <Input
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="name@deloitte.com"
                />
              </label>
              <label className="grid gap-1.5 text-2xs font-semibold uppercase tracking-wide text-[var(--text-muted)]">
                Role
                <Select value={role} onChange={(e) => setRole(e.target.value)}>
                  {MEMBER_ROLES.map((option) => (
                    <option key={option}>{option}</option>
                  ))}
                </Select>
              </label>
              <p className="text-xs text-[var(--text-muted)]">
                Existing organization accounts only. The invitation applies to this engagement. A second reviewer is
                optional: an author can review their own drafts.
              </p>
              <Button type="submit" disabled={change.isPending || !email.trim()}>
                Add member
              </Button>
            </form>
          </Card>
        ) : null}
      </div>
    </section>
  );
}

export function ActivitySection({ id }: { id: string }) {
  const activity = useEngagementActivityQuery(id);
  const [kind, setKind] = useState("all");
  if (activity.isPending) return <Skeleton className="h-64 w-full" />;
  const events = activity.data ?? [];
  const kinds = Array.from(new Set(events.map((e) => e.kind ?? "other")));
  const shown = kind === "all" ? events : events.filter((e) => (e.kind ?? "other") === kind);
  return (
    <Card className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-base font-semibold text-[var(--text-default)]">Engagement timeline · Newest first</h2>
        <Select aria-label="Activity filter" value={kind} onChange={(e) => setKind(e.target.value)} className="w-auto">
          <option value="all">All events</option>
          {kinds.map((option) => (
            <option key={option}>{option}</option>
          ))}
        </Select>
      </div>
      <ErrorNote error={activity.error} />
      {shown.length === 0 ? (
        <p className="text-sm text-[var(--text-muted)]">No activity recorded yet.</p>
      ) : (
        <ul className="divide-y divide-[var(--surface-border)]">
          {shown.map((event) => (
            <li key={event.id} className="py-3">
              <p className="text-sm font-semibold text-[var(--text-default)]">{event.title}</p>
              <p className="text-xs text-[var(--text-muted)]">{event.meta}</p>
              {event.detail ? <p className="mt-1 text-sm text-[var(--text-default)]">{event.detail}</p> : null}
            </li>
          ))}
        </ul>
      )}
      <p className="text-xs text-[var(--text-muted)]">
        Append-only history. Version and review events are retained for traceability; activity does not grant
        additional content access.
      </p>
    </Card>
  );
}

const BRIEF_FIELDS = [
  ["brief", "Objective"],
  ["sponsorObjective", "Sponsor objective"],
  ["scope", "Scope"],
  ["successMeasures", "Success measures"],
] as const;

export function BriefSection({ id, detail, onContinue }: SectionProps & { onContinue: () => void }) {
  const save = useUpdateEngagementMutation(id);
  const clean = (value: string) => (value === "—" ? "" : value);
  const [form, setForm] = useState({
    brief: detail.brief.summary.startsWith("No brief captured") ? "" : detail.brief.summary,
    sponsorObjective: clean(detail.brief.sponsorObjective),
    scope: clean(detail.brief.scope),
    successMeasures: clean(detail.brief.successMeasures),
  });
  return (
    <section className="grid gap-4 lg:grid-cols-[2fr_1fr]">
      <Card className="space-y-4">
        <h2 className="text-base font-semibold text-[var(--text-default)]">Engagement brief · {detail.brief.updated}</h2>
        {BRIEF_FIELDS.map(([key, label]) => (
          <label key={key} className="grid gap-1.5 text-2xs font-semibold uppercase tracking-wide text-[var(--text-muted)]">
            {label}
            <Textarea
              rows={key === "brief" ? 3 : 2}
              value={form[key]}
              onChange={(e) => setForm((prev) => ({ ...prev, [key]: e.target.value }))}
            />
          </label>
        ))}
        <ErrorNote error={save.error} />
        <div className="flex flex-wrap items-center gap-3">
          <Button disabled={save.isPending} onClick={() => save.mutate(form)}>
            {save.isPending ? "Saving…" : "Save brief"}
          </Button>
          {save.isSuccess ? <span className="text-sm text-[#356B12]">Brief saved.</span> : null}
        </div>
      </Card>
      <Card className="h-fit space-y-3">
        <h2 className="text-base font-semibold text-[var(--text-default)]">Workflow context</h2>
        <Field label="Timeline">{detail.dateRange}</Field>
        <Field label="Classification">{detail.brief.classification}</Field>
        <Field label="Source readiness">{detail.evidenceSourceCount} permitted sources</Field>
        <Button variant="secondary" className="w-full justify-center" onClick={onContinue}>
          Continue to Sources →
        </Button>
      </Card>
    </section>
  );
}

export function DraftSection({ id, detail }: SectionProps) {
  return (
    <section className="grid gap-4 lg:grid-cols-[2fr_1fr]">
      <Card className="space-y-3">
        <h2 className="text-base font-semibold text-[var(--text-default)]">Draft outputs &amp; readiness</h2>
        {detail.deliverables.length === 0 ? (
          <EmptyState
            title="No drafts yet"
            description="Start a conversation, then create PPTX and DOCX drafts from a grounded answer."
          />
        ) : (
          <ul className="divide-y divide-[var(--surface-border)]">
            {detail.deliverables.map((item) => (
              <li key={item.id} className="flex flex-wrap items-center justify-between gap-2 py-3">
                <div>
                  <p className="text-sm font-semibold text-[var(--text-default)]">{item.name}</p>
                  <p className="text-xs text-[var(--text-muted)]">{item.meta}</p>
                </div>
                {item.status ? <Badge variant="secondary">{item.status}</Badge> : null}
              </li>
            ))}
          </ul>
        )}
      </Card>
      <Card className="h-fit space-y-3">
        <h2 className="text-base font-semibold text-[var(--text-default)]">Create or continue</h2>
        <Link href={`/engagements/${id}/conversation`} className="block !no-underline">
          <Button className="w-full justify-center">Open conversation</Button>
        </Link>
        <Link href={`/engagements/${id}/deliverables`} className="block !no-underline">
          <Button variant="secondary" className="w-full justify-center">
            Open artifacts
          </Button>
        </Link>
        <p className="text-xs text-[var(--text-muted)]">
          Drafts are AI-assisted working versions. They need a review before export.
        </p>
      </Card>
    </section>
  );
}

export function ReviewSection({ detail }: { detail: EngagementDetail }) {
  const reviews = detail.deliverables.filter((item) => item.status && item.status !== "Draft");
  return (
    <Card className="space-y-3">
      <h2 className="text-base font-semibold text-[var(--text-default)]">Reviews for this engagement</h2>
      {reviews.length === 0 ? (
        <p className="text-sm text-[var(--text-muted)]">No artifact has been submitted for review yet.</p>
      ) : (
        <ul className="divide-y divide-[var(--surface-border)]">
          {reviews.map((item) => (
            <li key={item.id} className="flex flex-wrap items-center justify-between gap-2 py-3">
              <div>
                <p className="text-sm font-semibold text-[var(--text-default)]">
                  {item.name} · {item.id}
                </p>
                <p className="text-xs text-[var(--text-muted)]">
                  {item.meta} · {item.status}
                </p>
              </div>
              <Link href={`/reviews/${encodeURIComponent(item.id)}`} className="!no-underline">
                <Button variant="secondary" className="px-3 py-1.5 text-xs">
                  Open review
                </Button>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}

export function ExportSection({ id }: { id: string }) {
  const { api } = useAuth();
  const readiness = useExportReadinessQuery(id);
  const [error, setError] = useState<unknown>(null);
  if (readiness.isPending) return <Skeleton className="h-64 w-full" />;
  const data = readiness.data;
  if (!data) return <ErrorNote error={readiness.error} />;
  const runId = data.artifacts.find((a) => a.runId)?.runId ?? null;

  async function download(kind: "pptx" | "docx") {
    setError(null);
    try {
      await downloadFile(api, `/api/runs/${id}/${runId}/artifacts/${kind}/download`, `deliverable.${kind}`);
    } catch (err) {
      setError(err);
    }
  }

  return (
    <section className="grid gap-4 lg:grid-cols-[2fr_1fr]">
      <Card className="space-y-3">
        <h2 className="text-base font-semibold text-[var(--text-default)]">Artifacts &amp; approval gates</h2>
        <table className="w-full text-left text-sm">
          <thead className="text-xs text-[var(--text-muted)]">
            <tr>
              <th className="py-2 font-medium">Artifact</th>
              <th className="py-2 font-medium">Version</th>
              <th className="py-2 font-medium">Review</th>
              <th className="py-2 font-medium">Export</th>
            </tr>
          </thead>
          <tbody>
            {data.artifacts.map((artifact) => (
              <tr key={artifact.id} className="border-t border-[var(--surface-border)]">
                <td className="py-3 font-medium text-[var(--text-default)]">{artifact.name}</td>
                <td className="py-3">{artifact.version}</td>
                <td className="py-3">{artifact.review}</td>
                <td className="py-3">{artifact.export}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <p
          className={
            data.ready
              ? "rounded-md bg-[#EFF6E6] px-3 py-2 text-sm text-[#356B12]"
              : "rounded-md border border-[#F3E2C0] bg-[#FCF3E2] px-3 py-2 text-sm text-[#8C5B12]"
          }
        >
          <span className="block font-semibold">{data.ready ? "Export available" : "Export not yet available"}</span>
          {data.message}
        </p>
        <ErrorNote error={error} />
        <div className="flex flex-wrap gap-2">
          <Button disabled={!data.ready || !runId} onClick={() => void download("pptx")}>
            Download PPTX
          </Button>
          <Button variant="secondary" disabled={!data.ready || !runId} onClick={() => void download("docx")}>
            Download DOCX
          </Button>
          {data.blockers[0] ? (
            <Link href={`/reviews/${encodeURIComponent(data.blockers[0])}`} className="!no-underline">
              <Button variant="secondary">Open review</Button>
            </Link>
          ) : null}
        </div>
      </Card>
      <Card className="h-fit space-y-3">
        <h2 className="text-base font-semibold text-[var(--text-default)]">Export package</h2>
        <Field label="Formats">PowerPoint (.pptx) · Word (.docx)</Field>
        <Field label="Include">Evidence register · Classification footer</Field>
        <Field label="Destination">Internal sponsor review only</Field>
        <p className="text-xs text-[var(--text-muted)]">
          Source provenance and classification remain in the package. External sharing is not permitted.
        </p>
      </Card>
    </section>
  );
}
