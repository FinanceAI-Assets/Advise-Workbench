"use client";

import { ClipboardCheck, Download, Plus, Send } from "lucide-react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import {
  ArtifactViewer,
  DocumentOutline,
  EngagementFilesPanel,
  EvidenceRegisterView,
  ExportApprovalNotice,
  formatRunTime,
  SlideCanvas,
  SlideEvidencePanel,
  SlideNavigator,
  toPages,
  VersionHistoryPanel,
  WordArtifactPanel,
  WordDocumentReader,
} from "@/components/deliverables";
import { RunProgressCard } from "@/components/conversation/RunProgressCard";
import { EngagementTabs } from "@/components/engagements";
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
import type { ArtifactStatus } from "@/types/api";

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

const TAB_KEYS: DeliverableTabKey[] = ["all", "powerpoint", "word", "evidence-register"];
const TAB_CRUMB: Record<DeliverableTabKey, string> = {
  all: "",
  powerpoint: " / PowerPoint",
  word: " / Word",
  "evidence-register": " / Evidence register",
};

// Deliverables for one engagement: the latest run's deck, document and evidence register, each with its own
// tab, plus review submission and downloads that open once the version is approved.
export default function EngagementDeliverablesPage() {
  const params = useParams();
  const router = useRouter();
  const { api } = useAuth();
  const id = typeof params.id === "string" ? params.id : Array.isArray(params.id) ? (params.id[0] ?? "") : "";

  const deliverables = useDeliverablesQuery(id);
  const readiness = useExportReadinessQuery(id);
  const engagement = useEngagementDetailQuery(id);
  // When generation finishes, load the new drafts without a manual refresh.
  const latestRun = useRunProgressQuery(id).data?.run;
  const finishedRun = latestRun?.finished ? latestRun.id : "";
  const refetchDeliverables = deliverables.refetch;
  useEffect(() => {
    if (finishedRun) void refetchDeliverables();
  }, [finishedRun, refetchDeliverables]);
  const [tab, setTab] = useState<DeliverableTabKey>("all");
  const [slideIndex, setSlideIndex] = useState(0);
  const [docPage, setDocPage] = useState(0);
  const [submitting, setSubmitting] = useState<ArtifactKind | null>(null);
  const [downloadError, setDownloadError] = useState<unknown>(null);

  // Links such as ?tab=powerpoint (from the engagement's Deliverables tab) open that view.
  useEffect(() => {
    const requested = new URLSearchParams(window.location.search).get("tab") as DeliverableTabKey | null;
    // eslint-disable-next-line react-hooks/set-state-in-effect -- reading the URL once on mount
    if (requested && TAB_KEYS.includes(requested)) setTab(requested);
  }, []);

  if (deliverables.isPending) return <PageSkeleton />;

  const engagementName = deliverables.data?.engagementName ?? engagement.data?.name ?? "Engagement";
  const breadcrumb = (
    <>
      <Link href={`/engagements/${id}`}>{engagementName}</Link> / Deliverables{TAB_CRUMB[tab]}
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
  const code = engagement.data?.code ?? "";
  const sourceCount = engagement.data?.tabCounts.sources ?? 0;
  const reviews = (readiness.data?.artifacts ?? []).filter((a) => a.runId === runId);
  const reviewOf = (kind: ArtifactKind) => reviews.find((a) => a.type === kind);
  // A reviewed artifact has a real title, version and state; show those instead of the generic labels.
  const pptxReview = reviewOf("pptx");
  const docxReview = reviewOf("docx");
  const pptx = pptxReview
    ? { ...data.pptx, name: pptxReview.name, versionLabel: pptxReview.version, status: pptxReview.review as ArtifactStatus }
    : data.pptx;
  const docx = docxReview
    ? {
        ...data.docx,
        name: docxReview.name,
        versionLabel: docxReview.version.split(" ").pop() ?? "",
        status: docxReview.review as ArtifactStatus,
      }
    : data.docx;
  const files = data.files.map((file) => {
    const review = file.type === "pptx" ? pptxReview : file.type === "docx" ? docxReview : undefined;
    return review ? { ...file, name: review.name, status: review.review as ArtifactStatus } : file;
  });
  const canDownload = (kind: ArtifactKind) => reviewOf(kind)?.export === "Available";
  const hasPptx = data.tabCounts.powerpoint > 0;
  const hasDocx = data.tabCounts.word > 0;
  const pptxVersion = pptx.versionLabel.split(" ").pop() ?? "";
  const docxVersion = docx.versionLabel.split(" ").pop() ?? "";
  const unsupported = data.claims.filter((c) => !c.grounded).length;
  const slideLinks = data.claimsBySlideIndex[slideIndex] ?? [];

  const tabs = [
    { key: "all" as const, label: "All artifacts", count: data.tabCounts.all },
    { key: "powerpoint" as const, label: "PowerPoint", count: data.tabCounts.powerpoint },
    { key: "word" as const, label: "Word", count: data.tabCounts.word },
    { key: "evidence-register" as const, label: "Evidence register", count: data.tabCounts.evidenceRegister },
  ];

  const getSlideDetail = (index: number) =>
    toSlideDetail(data.rawSlides[index], index, data.rawSlides.length, data.slideBreadcrumb, data.slideSourcesSummary, data.slideFooterMeta);
  const claimCounts = Object.fromEntries(Object.entries(data.claimsBySlideIndex).map(([i, links]) => [i, links.length]));

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

  // Why downloads are still locked, artifact by artifact.
  const lockedReasons = (["pptx", "docx"] as const)
    .filter((kind) => (kind === "pptx" ? hasPptx : hasDocx) && !canDownload(kind))
    .map((kind) => {
      const review = reviewOf(kind);
      if (!review || review.review === "Draft") return `${kind.toUpperCase()} is not yet submitted`;
      return `${kind.toUpperCase()} is ${review.review.toLowerCase()}`;
    });
  const exportNotice = lockedReasons.length ? (
    <ExportApprovalNotice description={`${lockedReasons.join(". ")}. Downloads unlock after reviewer approval.`} />
  ) : null;

  const openTab = (key: DeliverableTabKey) => {
    setTab(key);
    setSubmitting(null);
  };

  const header: Record<DeliverableTabKey, { title: string; subtitle: string }> = {
    all: { title: data.title, subtitle: data.subtitle },
    powerpoint: {
      title: "PowerPoint artifact",
      subtitle: [pptx.name, `PPTX ${pptxVersion}`, `${pptx.slides.length} slides`, code].filter(Boolean).join(" · "),
    },
    word: {
      title: "Word artifact",
      subtitle: [docx.name, `DOCX ${docxVersion}`, `${docx.preview.sections.length} sections`, code].filter(Boolean).join(" · "),
    },
    "evidence-register": {
      title: "Evidence register",
      subtitle: `${sourceCount} permitted source${sourceCount === 1 ? "" : "s"} · Trace claims to versioned passages and artifact locations.`,
    },
  };

  const actions =
    tab === "powerpoint" && hasPptx ? (
      <Button type="button" className="flex items-center gap-2" onClick={reviewAction("pptx")}>
        <ClipboardCheck size={16} aria-hidden />
        {reviewLabel("pptx")}
      </Button>
    ) : tab === "word" && hasDocx ? (
      <Button type="button" className="flex items-center gap-2" onClick={reviewAction("docx")}>
        <Send size={16} aria-hidden />
        {reviewLabel("docx")}
      </Button>
    ) : tab === "all" ? (
      <Button type="button" className="flex items-center gap-2" onClick={() => router.push(`/engagements/${id}/conversation`)}>
        <Plus size={16} aria-hidden />
        Create deliverable
      </Button>
    ) : null;

  const empty = (what: string) => <EmptyState title="Nothing here yet" description={`This run did not produce ${what}.`} />;

  return (
    <PageFrame breadcrumb={breadcrumb} title={header[tab].title} subtitle={header[tab].subtitle} actions={actions}>
      <RunProgressCard pid={id} showArtifactsLink={false} />

      <EngagementTabs tabs={tabs} active={tab} onChange={openTab} />

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

      {tab === "all" ? (
        <div className="grid gap-4 lg:grid-cols-[240px_1fr] xl:grid-cols-[240px_1fr_320px]">
          <div className="space-y-4">
            <EngagementFilesPanel
              files={files}
              activeFileId=""
              onSelect={(fileId) => openTab(fileId === "pptx" ? "powerpoint" : fileId === "docx" ? "word" : "evidence-register")}
            />
            <VersionHistoryPanel versions={data.versions} />
          </div>
          <div className="space-y-4">
            {hasPptx ? (
              <>
                <ArtifactViewer
                  pptx={pptx}
                  getSlideDetail={getSlideDetail}
                  onSlideChange={setSlideIndex}
                  reviewLabel={reviewLabel("pptx")}
                  onOpenReview={reviewAction("pptx")}
                  onDownload={canDownload("pptx") ? () => void download("pptx") : undefined}
                />
                <SlideEvidencePanel links={slideLinks} />
              </>
            ) : (
              empty("a deck")
            )}
          </div>
          <div className="space-y-4 lg:col-span-2 xl:col-span-1">
            {hasDocx ? (
              <WordArtifactPanel
                docx={{ ...docx, preview: { ...docx.preview, pageLabel: `1 / ${toPages(docx.preview.sections).length}` } }}
                previewSections={2}
                onOpen={() => openTab("word")}
                onDownload={canDownload("docx") ? () => void download("docx") : undefined}
              />
            ) : null}
            {exportNotice}
          </div>
        </div>
      ) : null}

      {tab === "powerpoint" ? (
        hasPptx ? (
          <>
            <div className="grid gap-4 lg:grid-cols-[260px_1fr]">
              <SlideNavigator slides={pptx.slides} activeIndex={slideIndex} claimCounts={claimCounts} onSelect={setSlideIndex} />
              <Card className="space-y-4">
                <div className="flex flex-wrap items-baseline gap-2">
                  <h2 className="text-base font-semibold text-[var(--text-default)]">{pptx.name}</h2>
                  <span className="text-xs text-[var(--text-muted)]">
                    · Slide {slideIndex + 1} / {pptx.slides.length}
                  </span>
                </div>
                <SlideCanvas slide={getSlideDetail(slideIndex)} />
                <div className="flex flex-wrap gap-2">
                  <Button variant="secondary" type="button" disabled={slideIndex === 0} onClick={() => setSlideIndex(slideIndex - 1)}>
                    Previous
                  </Button>
                  <Button
                    variant="secondary"
                    type="button"
                    disabled={slideIndex >= pptx.slides.length - 1}
                    onClick={() => setSlideIndex(slideIndex + 1)}
                  >
                    Next
                  </Button>
                  <Button
                    variant="secondary"
                    type="button"
                    disabled={!canDownload("pptx")}
                    title={canDownload("pptx") ? undefined : "Available after independent approval"}
                    className="flex items-center gap-2"
                    onClick={() => void download("pptx")}
                  >
                    <Download size={16} aria-hidden />
                    Download PPTX
                  </Button>
                </div>
                <ul className="space-y-2 border-t border-[var(--surface-border)] pt-3">
                  {slideLinks.map((link) => (
                    <li key={link.id}>
                      <p className="text-sm font-semibold text-[var(--text-default)]">
                        [{link.index}] {link.label}{" "}
                        <span className={link.verified ? "text-xs font-medium text-[#356B12]" : "text-xs font-medium text-[#8C5B12]"}>
                          {link.verified ? "Verified" : "Needs caveat"}
                        </span>
                      </p>
                      <p className="text-xs text-[var(--text-muted)]">{link.description}</p>
                    </li>
                  ))}
                  {slideLinks.length === 0 ? <li className="text-xs text-[var(--text-muted)]">No claims recorded for this slide.</li> : null}
                </ul>
              </Card>
            </div>
            {exportNotice}
          </>
        ) : (
          empty("a deck")
        )
      ) : null}

      {tab === "word" ? (
        hasDocx ? (
          <div className="grid gap-4 lg:grid-cols-[260px_1fr]">
            <DocumentOutline sections={docx.preview.sections} page={docPage} onSelectPage={setDocPage} />
            <WordDocumentReader
              docx={docx}
              page={docPage}
              onPageChange={setDocPage}
              assumption={
                unsupported
                  ? {
                      title: "Assumptions to caveat",
                      description: `${unsupported} claim${unsupported === 1 ? " has" : "s have"} no validated source. Do not present ${
                        unsupported === 1 ? "it" : "them"
                      } as established fact; see the evidence register.`,
                    }
                  : null
              }
              reviewLabel={reviewLabel("docx")}
              onReview={reviewAction("docx")}
              onDownload={canDownload("docx") ? () => void download("docx") : undefined}
            />
          </div>
        ) : (
          empty("a document")
        )
      ) : null}

      {tab === "evidence-register" ? (
        <EvidenceRegisterView
          pid={id}
          claims={data.claims}
          sourceCount={sourceCount}
          evaluatedAt={formatRunTime(data.run.createdAt)}
          outputs={[hasPptx && `PPTX ${pptxVersion}`, hasDocx && `DOCX ${docxVersion}`, "Version-pinned citations"].filter(Boolean).join(" · ")}
        />
      ) : null}
    </PageFrame>
  );
}
