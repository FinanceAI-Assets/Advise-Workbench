"use client";

import { Download, Plus, Send } from "lucide-react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import {
  ArtifactViewer,
  EngagementFilesPanel,
  SlideEvidencePanel,
  VersionHistoryPanel,
  WordArtifactPanel,
} from "@/components/deliverables";
import { RunProgressCard } from "@/components/conversation/RunProgressCard";
import { EngagementTabs } from "@/components/engagements";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { Input } from "@/components/ui/Input";
import { Select } from "@/components/ui/Select";
import { ErrorNote, PageFrame, PageSkeleton } from "@/components/workbench/PageFrame";
import { useDeliverablesQuery } from "@/hooks/useDeliverables";
import { useEngagementDetailQuery, useExportReadinessQuery } from "@/hooks/useEngagements";
import { useRunProgressQuery, useSubmitForReviewMutation } from "@/hooks/useWorkbench";
import { useAuth } from "@/lib/auth-context";
import { toSlideDetail } from "@/lib/deliverableAdapters";
import { downloadFile } from "@/lib/workbenchApi";

type DeliverableTabKey = "all" | "powerpoint" | "word" | "evidence-register";
type ArtifactKind = "pptx" | "docx";

/** Send one artifact of the run for review: to another member, or to yourself. */
function SubmitForReview({
  pid,
  runId,
  kind,
  title,
  onDone,
}: {
  pid: string;
  runId: string;
  kind: ArtifactKind;
  title: string;
  onDone: () => void;
}) {
  const { user } = useAuth();
  const engagement = useEngagementDetailQuery(pid);
  const submit = useSubmitForReviewMutation();
  // Other members first, so a second pair of eyes is the default; you can always review it yourself.
  const members = (engagement.data?.teamMembers ?? []).filter((m) => m.userId);
  const reviewers = [...members.filter((m) => m.userId !== user?.id), ...members.filter((m) => m.userId === user?.id)];
  const [reviewerId, setReviewerId] = useState("");
  const [name, setName] = useState(title);
  const [dueDate, setDueDate] = useState("");
  const chosen = reviewerId || reviewers[0]?.userId || "";

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    await submit.mutateAsync({ projectId: pid, runId, artifactType: kind, title: name.trim(), reviewerId: chosen, dueDate });
    onDone();
  }

  return (
    <Card>
      <form onSubmit={(e) => void onSubmit(e)} className="grid gap-3 md:grid-cols-4 md:items-end">
        <label className="grid gap-1.5 text-2xs font-semibold uppercase tracking-wide text-[var(--text-muted)]">
          Artifact title
          <Input required minLength={3} value={name} onChange={(e) => setName(e.target.value)} />
        </label>
        <label className="grid gap-1.5 text-2xs font-semibold uppercase tracking-wide text-[var(--text-muted)]">
          Reviewer
          <Select required value={chosen} onChange={(e) => setReviewerId(e.target.value)}>
            {reviewers.map((member) => (
              <option key={member.id} value={member.userId}>
                {member.userId === user?.id ? `${member.name} (me, self-review)` : `${member.name} · ${member.role}`}
              </option>
            ))}
          </Select>
        </label>
        <label className="grid gap-1.5 text-2xs font-semibold uppercase tracking-wide text-[var(--text-muted)]">
          Due date
          <Input type="date" value={dueDate} onChange={(e) => setDueDate(e.target.value)} />
        </label>
        <div className="flex gap-2">
          <Button type="submit" disabled={!chosen || submit.isPending}>
            {submit.isPending ? "Submitting…" : `Submit ${kind.toUpperCase()}`}
          </Button>
          <Button type="button" variant="secondary" onClick={onDone}>
            Cancel
          </Button>
        </div>
        <div className="md:col-span-4">
          {chosen === user?.id ? (
            <p className="text-xs text-[var(--text-muted)]">
              You will review this yourself. It is recorded as a self-review; add another member under Manage access if
              you want a second reviewer.
            </p>
          ) : null}
          <ErrorNote error={submit.error} />
        </div>
      </form>
    </Card>
  );
}

// Deliverables for one engagement: the latest run's deck, document and evidence register,
// with review submission and downloads that open once the version is approved.
export default function EngagementDeliverablesPage() {
  const params = useParams();
  const router = useRouter();
  const { api } = useAuth();
  const id = typeof params.id === "string" ? params.id : Array.isArray(params.id) ? (params.id[0] ?? "") : "";

  const deliverables = useDeliverablesQuery(id);
  const readiness = useExportReadinessQuery(id);
  // When generation finishes, load the new drafts without a manual refresh.
  const latestRun = useRunProgressQuery(id).data?.run;
  const finishedRun = latestRun?.finished ? latestRun.id : "";
  const refetchDeliverables = deliverables.refetch;
  useEffect(() => {
    if (finishedRun) void refetchDeliverables();
  }, [finishedRun, refetchDeliverables]);
  const [tab, setTab] = useState<DeliverableTabKey>("all");
  const [activeFileId, setActiveFileId] = useState<string | null>(null);
  const [slideIndex, setSlideIndex] = useState(0);
  const [submitting, setSubmitting] = useState<ArtifactKind | null>(null);
  const [downloadError, setDownloadError] = useState<unknown>(null);

  if (deliverables.isPending) return <PageSkeleton />;

  const breadcrumb = (
    <>
      <Link href={`/engagements/${id}`}>{deliverables.data?.engagementName ?? "Engagement"}</Link> / Deliverables
    </>
  );

  if (deliverables.isError || !deliverables.data) {
    return (
      <PageFrame breadcrumb={breadcrumb} title="Deliverables & artifacts">
        <RunProgressCard pid={id} showArtifactsLink={false} />
        <ErrorNote error={deliverables.error} />
        <EmptyState
          title="No drafts yet"
          description="This engagement has no runs yet, so there are no deliverables to show. Start a conversation to create one."
        >
          <Link href={`/engagements/${id}/conversation`}>
            <Button type="button">Open conversation</Button>
          </Link>
        </EmptyState>
      </PageFrame>
    );
  }

  const data = deliverables.data;
  const runId = data.runId;
  const reviews = (readiness.data?.artifacts ?? []).filter((a) => a.runId === runId);
  const reviewOf = (kind: ArtifactKind) => reviews.find((a) => a.type === kind);
  // A reviewed artifact has a real title and version; show those instead of the generic labels.
  const pptxReview = reviewOf("pptx");
  const docxReview = reviewOf("docx");
  const pptx = pptxReview ? { ...data.pptx, name: pptxReview.name, versionLabel: pptxReview.version } : data.pptx;
  const docx = docxReview ? { ...data.docx, name: docxReview.name, versionLabel: docxReview.version } : data.docx;
  const named = data.files.map((file) => {
    const review = file.type === "pptx" ? pptxReview : file.type === "docx" ? docxReview : undefined;
    return review ? { ...file, name: review.name } : file;
  });
  const canDownload = (kind: ArtifactKind) => reviewOf(kind)?.export === "Available";

  const files =
    tab === "powerpoint"
      ? named.filter((f) => f.type === "pptx")
      : tab === "word"
        ? named.filter((f) => f.type === "docx")
        : tab === "evidence-register"
          ? named.filter((f) => f.type === "evidence")
          : named;
  const selectedFile = files.find((f) => f.id === activeFileId) ?? files[0];
  const claims = Object.entries(data.claimsBySlideIndex).flatMap(([index, links]) =>
    links.map((link) => ({ ...link, slide: Number(index) + 1 }))
  );

  const tabs = [
    { key: "all" as const, label: "All artifacts", count: data.tabCounts.all },
    { key: "powerpoint" as const, label: "PowerPoint", count: data.tabCounts.powerpoint },
    { key: "word" as const, label: "Word", count: data.tabCounts.word },
    { key: "evidence-register" as const, label: "Evidence register", count: data.tabCounts.evidenceRegister },
  ];

  const getSlideDetail = (index: number) =>
    toSlideDetail(data.rawSlides[index], index, data.rawSlides.length, data.slideBreadcrumb, data.slideSourcesSummary, data.slideFooterMeta);

  async function download(kind: ArtifactKind) {
    setDownloadError(null);
    try {
      await downloadFile(api, `/api/runs/${id}/${runId}/artifacts/${kind}/download`, `${data.engagementName}.${kind}`);
    } catch (err) {
      setDownloadError(err);
    }
  }

  function reviewAction(kind: ArtifactKind) {
    const review = reviewOf(kind);
    if (review && review.review !== "Draft") return () => router.push(`/reviews/${encodeURIComponent(review.id)}`);
    return () => setSubmitting(kind);
  }

  const reviewLabel = (kind: ArtifactKind) => {
    const review = reviewOf(kind);
    return review && review.review !== "Draft" ? `Open review · ${review.review}` : "Submit for review";
  };

  return (
    <PageFrame
      breadcrumb={breadcrumb}
      title={data.title}
      subtitle={data.subtitle}
      actions={
        <>
          {(["pptx", "docx"] as const)
            .filter((kind) => data.files.some((f) => f.type === kind))
            .map((kind) => (
              <Button
                key={kind}
                type="button"
                variant={canDownload(kind) ? "primary" : "secondary"}
                disabled={!canDownload(kind)}
                title={canDownload(kind) ? undefined : "Available after the review is approved"}
                className="flex items-center gap-2"
                onClick={() => void download(kind)}
              >
                <Download size={16} aria-hidden />
                Download {kind.toUpperCase()}
              </Button>
            ))}
          <Button
            type="button"
            variant="secondary"
            className="flex items-center gap-2"
            onClick={() => router.push(`/engagements/${id}/conversation`)}
          >
            <Plus size={16} aria-hidden />
            Create deliverable
          </Button>
        </>
      }
    >
      <RunProgressCard pid={id} showArtifactsLink={false} />

      <EngagementTabs
        tabs={tabs}
        active={tab}
        onChange={(key) => {
          setTab(key);
          setActiveFileId(null);
        }}
      />

      {submitting ? (
        <SubmitForReview
          pid={id}
          runId={runId}
          kind={submitting}
          title={submitting === "pptx" ? pptx.name : docx.name}
          onDone={() => setSubmitting(null)}
        />
      ) : null}
      <ErrorNote error={downloadError} />

      {files.length === 0 ? (
        <EmptyState title="Nothing here yet" description="This run did not produce an artifact of this type." />
      ) : (
        <div className="grid gap-4 lg:grid-cols-[280px_1fr]">
          <div className="space-y-4">
            <EngagementFilesPanel files={files} activeFileId={selectedFile?.id ?? ""} onSelect={setActiveFileId} />
            <VersionHistoryPanel versions={data.versions} />
          </div>

          <div className="space-y-4">
            {selectedFile?.type === "pptx" ? (
              <>
                <ArtifactViewer
                  pptx={pptx}
                  getSlideDetail={getSlideDetail}
                  onSlideChange={setSlideIndex}
                  reviewLabel={reviewLabel("pptx")}
                  onOpenReview={reviewAction("pptx")}
                  onDownload={canDownload("pptx") ? () => void download("pptx") : undefined}
                />
                <SlideEvidencePanel links={data.claimsBySlideIndex[slideIndex] ?? []} />
              </>
            ) : null}

            {selectedFile?.type === "docx" ? (
              <>
                <WordArtifactPanel docx={docx} onDownload={canDownload("docx") ? () => void download("docx") : undefined} />
                <Button variant="secondary" className="flex items-center gap-2" onClick={reviewAction("docx")}>
                  <Send size={16} aria-hidden />
                  {reviewLabel("docx")}
                </Button>
              </>
            ) : null}

            {selectedFile?.type === "evidence" ? (
              <Card className="space-y-3">
                <div className="flex items-center justify-between">
                  <h2 className="text-base font-semibold text-[var(--text-default)]">Evidence register</h2>
                  <span className="text-xs text-[var(--text-muted)]">
                    {claims.filter((c) => c.verified).length} of {claims.length} claims cited
                  </span>
                </div>
                <table className="w-full text-left text-sm">
                  <thead className="text-xs text-[var(--text-muted)]">
                    <tr>
                      <th className="py-2 font-medium">Claim</th>
                      <th className="py-2 font-medium">Slide</th>
                      <th className="py-2 font-medium">Source</th>
                      <th className="py-2 font-medium">Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {claims.map((claim) => (
                      <tr key={claim.id} className="border-t border-[var(--surface-border)] align-top">
                        <td className="py-3 pr-3 text-[var(--text-default)]">{claim.label}</td>
                        <td className="py-3 pr-3">{claim.slide}</td>
                        <td className="py-3 pr-3 text-[var(--text-muted)]">{claim.description}</td>
                        <td className="py-3">
                          <Badge variant={claim.verified ? "success" : "warning"}>
                            {claim.verified ? "Cited" : "Unsupported"}
                          </Badge>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                <p className="text-xs text-[var(--text-muted)]">
                  Unsupported claims must be given a source or marked as assumptions before approval.
                </p>
              </Card>
            ) : null}
          </div>
        </div>
      )}
    </PageFrame>
  );
}
