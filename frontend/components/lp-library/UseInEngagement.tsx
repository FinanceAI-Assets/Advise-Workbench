"use client";

import { ArrowLeft, Check, CheckCircle2, ShieldAlert, X } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";

import type { DiscoveryTurn, SelectedSource } from "@/components/lp-library/TalkToData";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Input } from "@/components/ui/Input";
import { Select } from "@/components/ui/Select";
import { Textarea } from "@/components/ui/Textarea";
import { ErrorNote, PageFrame } from "@/components/workbench/PageFrame";
import { useEngagementDetailQuery } from "@/hooks/useEngagements";
import { useConversationContextQuery, useLibraryHandoffMutation, useMyEngagementOptionsQuery } from "@/hooks/useWorkbench";
import { useAuth } from "@/lib/auth-context";
import { cn } from "@/lib/utils";

const ARTIFACTS = [
  { id: "pptx", label: "PPTX · Leadership deck" },
  { id: "docx", label: "DOCX · Recommendations memo" },
] as const;
type ArtifactId = (typeof ARTIFACTS)[number]["id"];

const label = "text-2xs font-semibold uppercase tracking-wide text-[var(--text-muted)]";

function Steps() {
  const steps = ["Discover & select", "Review & hand off", "Continue in Sheldon"];
  return (
    <ol className="flex flex-wrap items-center gap-x-6 gap-y-2 rounded-lg border border-[var(--surface-border)] bg-white px-4 py-2.5 text-xs">
      {steps.map((step, i) => (
        <li
          key={step}
          aria-current={i === 1 ? "step" : undefined}
          className={cn(
            "flex items-center gap-1.5",
            i === 0 && "text-[var(--accent-green-dark)]",
            i === 1 && "font-semibold text-[var(--text-default)]",
            i === 2 && "text-[var(--text-muted)]"
          )}
        >
          {i === 0 ? <Check size={14} aria-hidden /> : <span>{i + 1}</span>}
          {step}
        </li>
      ))}
    </ol>
  );
}

function Notice({ ok, title, children }: { ok: boolean; title: string; children: string }) {
  return (
    <div
      className={cn(
        "flex items-start gap-2 rounded-lg border p-3",
        ok ? "border-[#CFE3B5] bg-[#EFF6E6]" : "border-[#F3E2C0] bg-[#FCF3E2]"
      )}
      role={ok ? undefined : "alert"}
    >
      {ok ? (
        <CheckCircle2 size={16} className="mt-0.5 shrink-0 text-[var(--accent-green-dark)]" aria-hidden />
      ) : (
        <ShieldAlert size={16} className="mt-0.5 shrink-0 text-[#8C5B12]" aria-hidden />
      )}
      <div>
        <p className={cn("text-sm font-semibold", ok ? "text-[var(--text-default)]" : "text-[#8C5B12]")}>{title}</p>
        <p className={cn("text-xs", ok ? "text-[var(--text-muted)]" : "text-[#8C5B12]")}>{children}</p>
      </div>
    </div>
  );
}

/** The opening brief: what was asked in Talk to data and which guidance was chosen. Editable before handoff. */
function initialBrief(turns: DiscoveryTurn[], sources: SelectedSource[]): string {
  const asked = turns.filter((t) => t.answer).map((t) => t.question);
  const objective = asked[0] ?? "Use the selected leading practices in this engagement.";
  const follow = asked.slice(1).map((q) => `Also consider: ${q}`);
  const guidance = `Use the selected guidance: ${sources.map((s) => s.title).join("; ")}.`;
  return [objective, ...follow, guidance, "Flag assumptions and do not invent quantified benefits."].join("\n");
}

/** Review sources & use in engagement: carry the checked sources and an editable brief into a Sheldon conversation. */
export function UseInEngagement({
  turns,
  sources,
  onRemove,
  onBack,
}: {
  turns: DiscoveryTurn[];
  sources: SelectedSource[];
  onRemove: (practiceId: string) => void;
  onBack: () => void;
}) {
  const router = useRouter();
  const { user } = useAuth();
  const engagements = useMyEngagementOptionsQuery();
  const rows = engagements.data?.items ?? [];
  const [projectId, setProjectId] = useState("");
  const target = projectId || rows[0]?.id || "";
  const engagement = useEngagementDetailQuery(target);
  const context = useConversationContextQuery(target);
  const conversations = context.data?.items ?? [];
  const [mode, setMode] = useState<"existing" | "new" | "">("");
  const [conversationId, setConversationId] = useState("");
  const [title, setTitle] = useState(() => (turns.find((t) => t.answer)?.question ?? "Library discovery").slice(0, 80));
  const [brief, setBrief] = useState(() => initialBrief(turns, sources));
  const [artifacts, setArtifacts] = useState<Set<ArtifactId>>(() => new Set(["pptx", "docx"]));
  const [previewId, setPreviewId] = useState("");
  const handoff = useLibraryHandoffMutation();

  const firstAsked = turns.find((t) => t.answer);
  const activeMode = mode || (conversations.length ? "existing" : "new");
  const pickedConversation = conversationId || conversations.find((c) => c.active)?.id || conversations[0]?.id || "";
  const conversationLabel =
    activeMode === "new" ? title.trim() || "New conversation" : conversations.find((c) => c.id === pickedConversation)?.label ?? "";
  const preview = sources.find((s) => s.practiceId === previewId) ?? sources[0];

  // Adding a source needs an Owner or Editor role in the engagement (require_project_role on the API).
  const me = engagement.data?.teamMembers.find((m) => m.userId && m.userId === user?.id);
  const permission = !target || engagement.isPending ? "checking" : me && me.role !== "Viewer" ? "passed" : "failed";
  const engagementName = engagement.data?.name ?? "this engagement";

  const ready =
    sources.length > 0 &&
    permission === "passed" &&
    (activeMode === "new" ? title.trim().length >= 3 : Boolean(pickedConversation)) &&
    !handoff.isPending;

  const toggleArtifact = (id: ArtifactId) =>
    setArtifacts((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });

  const submit = () => {
    if (!ready) return;
    const intent = ARTIFACTS.filter((a) => artifacts.has(a.id)).map((a) => a.label);
    const draft = [
      brief.trim(),
      intent.length ? `Artifacts to prepare after review: ${intent.join(", ")}.` : "",
      `Sources: ${sources.map((s) => `${s.code} ${s.title}${s.version ? ` (${s.version})` : ""}`).join("; ")}.`,
    ]
      .filter(Boolean)
      .join("\n\n");
    handoff.mutate(
      {
        projectId: target,
        practiceIds: sources.map((s) => s.practiceId),
        conversation: activeMode === "new" ? { title: title.trim() } : { id: pickedConversation },
        brief: draft,
      },
      { onSuccess: ({ projectId: pid }) => router.push(`/engagements/${encodeURIComponent(pid)}/conversation`) }
    );
  };

  return (
    <PageFrame
      breadcrumb="Leading Practice Library / Talk to data / Use in engagement"
      title="Review sources & use in engagement"
      subtitle="Carry your chosen evidence and discovery brief into Sheldon. Source access rules stay with the conversation."
      actions={
        <Button variant="secondary" className="flex items-center gap-2" onClick={onBack}>
          <ArrowLeft size={16} aria-hidden />
          Back to discovery
        </Button>
      }
    >
      <Steps />

      <div className="grid gap-4 lg:grid-cols-2">
        <div className="space-y-4">
          <Card className="space-y-3">
            <div>
              <h2 className="text-base font-semibold text-[var(--text-default)]">Selected sources · {sources.length}</h2>
              <p className="text-xs text-[var(--text-muted)]">
                Exactly {sources.length === 1 ? "this source" : `these ${sources.length} sources`} will be attached. Use × to
                remove a source before continuing.
              </p>
            </div>
            {sources.length === 0 ? (
              <p className="rounded-lg border border-dashed border-[var(--surface-border)] p-3 text-sm text-[var(--text-muted)]">
                No sources left. Go back to discovery and check the ones you want to use.
              </p>
            ) : (
              <ul className="space-y-2">
                {sources.map((s, i) => (
                  <li
                    key={s.practiceId}
                    className={cn(
                      "flex items-start gap-3 rounded-lg border bg-white p-3",
                      preview?.practiceId === s.practiceId ? "border-[var(--accent-green)]" : "border-[var(--surface-border)]"
                    )}
                  >
                    <span className="rounded bg-[#EFF6E6] px-1.5 py-0.5 text-2xs font-semibold text-[#356B12]">[{i + 1}]</span>
                    <button type="button" className="min-w-0 flex-1 text-left" onClick={() => setPreviewId(s.practiceId)}>
                      <span className="block text-sm font-semibold text-[var(--text-default)]">{s.title}</span>
                      <span className="block text-2xs text-[var(--text-muted)]">
                        {[s.code, s.version, s.section].filter(Boolean).join(" · ")}
                      </span>
                      <span className="block text-2xs text-[var(--text-muted)]">{[s.owner, s.approved].filter(Boolean).join(" · ")}</span>
                    </button>
                    <button
                      type="button"
                      onClick={() => onRemove(s.practiceId)}
                      aria-label={`Remove ${s.title}`}
                      className="rounded p-1 text-[var(--text-muted)] transition hover:bg-[var(--primary-50)] hover:text-[var(--text-default)]"
                    >
                      <X size={14} aria-hidden />
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </Card>

          {preview ? (
            <Card className="space-y-2">
              <h2 className="text-base font-semibold text-[var(--text-default)]">Passage preview</h2>
              <div className="flex items-center justify-between gap-2">
                <p className="text-xs font-semibold text-[#356B12]">
                  {preview.code} · {preview.title}
                </p>
                {preview.version || preview.section ? (
                  <span className="rounded-md border border-[var(--surface-border)] px-2 py-0.5 text-2xs text-[var(--text-muted)]">
                    {[preview.version, preview.section].filter(Boolean).join(" · ")}
                  </span>
                ) : null}
              </div>
              <blockquote className="rounded-md bg-[var(--alabaster)] p-3 text-sm leading-relaxed text-[var(--text-default)]">
                &ldquo;{preview.passage}&rdquo;
              </blockquote>
              <p className="text-2xs text-[var(--text-muted)]">{[preview.owner, preview.approved].filter(Boolean).join(" · ")}</p>
            </Card>
          ) : null}

          {permission === "checking" ? (
            <p className="text-xs text-[var(--text-muted)]">Checking your access to the engagement…</p>
          ) : (
            <Notice
              ok={permission === "passed"}
              title={
                permission === "passed"
                  ? `Permission checks passed · ${sources.length} of ${sources.length}`
                  : "You cannot add sources to this engagement"
              }
            >
              {permission === "passed"
                ? `You can add ${sources.length === 1 ? "this approved practice" : `all ${sources.length} approved practices`} to ${engagementName}. Engagement classification and source access rules stay enforced in the conversation.`
                : `Adding sources needs an Owner or Editor role in ${engagementName}. Ask the engagement lead for access, or choose another engagement.`}
            </Notice>
          )}
        </div>

        <div className="space-y-4">
          <Card className="space-y-3">
            <h2 className="text-base font-semibold text-[var(--text-default)]">Destination & conversation</h2>
            <label className="grid gap-1.5">
              <span className={label}>Target engagement</span>
              <Select
                value={target}
                onChange={(e) => {
                  setProjectId(e.target.value);
                  setMode("");
                  setConversationId("");
                }}
                disabled={!rows.length}
              >
                {rows.length ? null : <option value="">{engagements.isPending ? "Loading…" : "No active engagements"}</option>}
                {rows.map((row) => (
                  <option key={row.id} value={row.id}>
                    {row.name} · {row.code}
                  </option>
                ))}
              </Select>
            </label>
            {engagement.data ? (
              <p className="text-2xs text-[var(--text-muted)]">
                {engagement.data.lead} · Engagement lead · {engagement.data.teamMemberCount} team member
                {engagement.data.teamMemberCount === 1 ? "" : "s"}
                {engagement.data.brief?.classification ? ` · ${engagement.data.brief.classification}` : ""}
              </p>
            ) : null}

            <fieldset className="space-y-2">
              <legend className={label}>Target · Sheldon conversation</legend>
              <div className="grid gap-2 sm:grid-cols-2">
                {(
                  [
                    ["existing", "Existing conversation"],
                    ["new", "New conversation"],
                  ] as const
                ).map(([value, text]) => (
                  <label
                    key={value}
                    className={cn(
                      "flex cursor-pointer items-center gap-2 rounded-md border px-3 py-2 text-sm",
                      activeMode === value
                        ? "border-[var(--accent-green)] bg-[#EFF6E6] font-semibold text-[var(--text-default)]"
                        : "border-[var(--surface-border)] text-[var(--text-muted)]",
                      value === "existing" && !conversations.length && "cursor-not-allowed opacity-60"
                    )}
                  >
                    <input
                      type="radio"
                      name="conversation-mode"
                      className="accent-[var(--accent-green)]"
                      checked={activeMode === value}
                      disabled={value === "existing" && !conversations.length}
                      onChange={() => setMode(value)}
                    />
                    {text}
                  </label>
                ))}
              </div>
            </fieldset>
            {activeMode === "existing" ? (
              <label className="grid gap-1.5">
                <span className={label}>Existing Sheldon conversation</span>
                <Select value={pickedConversation} onChange={(e) => setConversationId(e.target.value)}>
                  {conversations.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.label}
                      {c.updated ? ` · ${c.updated}` : ""}
                    </option>
                  ))}
                </Select>
              </label>
            ) : (
              <label className="grid gap-1.5">
                <span className={label}>New conversation title</span>
                <Input value={title} onChange={(e) => setTitle(e.target.value)} minLength={3} maxLength={120} />
              </label>
            )}
          </Card>

          <Card className="space-y-3">
            <div className="flex items-start justify-between gap-2">
              <div>
                <h2 className="text-base font-semibold text-[var(--text-default)]">Discovery context & artifact intent</h2>
                <p className="text-2xs text-[var(--text-muted)]">From Talk to data{firstAsked ? ` · ${firstAsked.at}` : ""}</p>
              </div>
              <span className="rounded-md border border-[var(--surface-border)] px-2 py-0.5 text-2xs text-[var(--text-muted)]">
                Editable brief
              </span>
            </div>
            <label className="grid gap-1.5">
              <span className={label}>Handoff brief · edit before continuing</span>
              <Textarea rows={6} value={brief} onChange={(e) => setBrief(e.target.value)} maxLength={4000} className="rounded-md" />
            </label>
            <fieldset className="space-y-1.5">
              <legend className={label}>Artifact intent</legend>
              <div className="flex flex-wrap gap-4">
                {ARTIFACTS.map((a) => (
                  <label key={a.id} className="flex items-center gap-2 text-sm text-[var(--text-default)]">
                    <input
                      type="checkbox"
                      className="h-4 w-4 accent-[var(--accent-green)]"
                      checked={artifacts.has(a.id)}
                      onChange={() => toggleArtifact(a.id)}
                    />
                    {a.label}
                  </label>
                ))}
              </div>
              <p className="text-2xs text-[var(--text-muted)]">
                Artifacts are not generated on handoff. Send the brief, review Sheldon&apos;s grounded response, then choose Create PPTX + DOCX drafts.
              </p>
            </fieldset>
          </Card>

          <Notice ok title="Only checked sources are transferred">
            Unchecked results and their passages stay in discovery. Your edited brief carries the discovery objective, not the
            full broad-discovery answer.
          </Notice>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-4 rounded-lg border border-[var(--surface-border)] bg-white p-4 shadow-sm">
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-semibold text-[var(--text-default)]">
            {sources.length} source{sources.length === 1 ? "" : "s"} → {engagement.data?.name ?? "engagement"} → Sheldon
            {conversationLabel ? ` / ${conversationLabel}` : ""}
          </p>
          <p className="text-2xs text-[var(--text-muted)]">
            Existing artifacts are unchanged. Human review is required before export.
          </p>
          <ErrorNote error={handoff.error} />
        </div>
        <Button variant="secondary" type="button" onClick={onBack}>
          Cancel
        </Button>
        <Button type="button" onClick={submit} disabled={!ready} className="flex items-center gap-2">
          <Check size={16} aria-hidden />
          {handoff.isPending ? "Adding sources…" : "Add sources & open conversation"}
        </Button>
      </div>
    </PageFrame>
  );
}
