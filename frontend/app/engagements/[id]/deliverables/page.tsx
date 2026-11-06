"use client";

import { Download, Loader2, Plus } from "lucide-react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import {
  ArtifactApproval,
  DeckDecisionButtons,
  EvidenceRegisterView,
  ExportApprovalNotice,
  formatRunTime,
  RegeneratingNotice,
  RegeneratingSlideOverlay,
  SlideCanvas,
  SlideNavigator,
  SlideReviewBar,
  type SlideReview,
  VersionHistoryPanel,
} from "@/components/deliverables";
import { RunProgressCard } from "@/components/conversation/RunProgressCard";
import { Badge, type BadgeVariant } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { BackButton } from "@/components/workbench/BackButton";
import { ErrorNote, PageFrame, PageSkeleton } from "@/components/workbench/PageFrame";
import { useDeliverablesQuery, useSlideDecisions } from "@/hooks/useDeliverables";
import { type ArtifactDesignReview, useArtifactDesignReview, useDeckDesignReview } from "@/hooks/usePhase5Review";
import { useEngagementDetailQuery, useExportReadinessQuery } from "@/hooks/useEngagements";
import { useRunProgressQuery } from "@/hooks/useWorkbench";
import { useAuth } from "@/lib/auth-context";
import { toSlideDetail } from "@/lib/deliverableAdapters";
import { downloadFile } from "@/lib/workbenchApi";
import type { ArtifactStatus } from "@/types/api";

type DeliverableView = "list" | "powerpoint" | "word" | "evidence-register";
type ArtifactKind = "pptx" | "docx";

const VIEWS: DeliverableView[] = ["list", "powerpoint", "word", "evidence-register"];
const VIEW_CRUMB: Record<DeliverableView, string> = {
  list: "",
  powerpoint: " / PowerPoint",
  word: " / Word",
  "evidence-register": " / Evidence register",
};
// A Word draft is reviewed under whichever output the run requested for it.
const WORD_REVIEW_TYPES = ["docx", "narrative", "sop"];

/** Review state of an artifact as the list shows it. */
type ReviewState = { label: string; variant: BadgeVariant; busy?: boolean };

function reviewState(design: ArtifactDesignReview | null): ReviewState {
  if (!design) return { label: "Draft", variant: "secondary" };
  if (design.approved) return { label: "Approved", variant: "success" };
  if (design.regenerating) return { label: `Regenerating ${design.version}`, variant: "info", busy: true };
  if (design.waiting) return { label: "Awaiting approval", variant: "warning" };
  return { label: "Not approved", variant: "secondary" };
}

type ListItem = { view: DeliverableView; name: string; meta: string; state?: ReviewState };

/** The run's artifacts, grouped by kind; choosing one opens it. */
function ArtifactList({ groups, onOpen }: { groups: Array<{ title: string; items: ListItem[] }>; onOpen: (view: DeliverableView) => void }) {
  return (
    <Card className="space-y-4">
      <h2 className="text-base font-semibold text-[var(--text-default)]">Generated artifacts</h2>
      {groups.map((group) => (
        <section key={group.title} className="space-y-2">
          <h3 className="text-2xs font-semibold uppercase tracking-wide text-[var(--text-muted)]">{group.title}</h3>
          <ul className="divide-y divide-[var(--surface-border)] rounded-lg border border-[var(--surface-border)]">
            {group.items.map((item) => (
              <li key={item.view}>
                <button
                  type="button"
                  onClick={() => onOpen(item.view)}
                  className="flex w-full flex-wrap items-center justify-between gap-2 px-4 py-3 text-left transition hover:bg-[var(--surface-muted)]"
                >
                  <span>
                    <span className="block text-sm font-semibold text-[var(--text-default)]">{item.name}</span>
                    <span className="block text-xs text-[var(--text-muted)]">{item.meta}</span>
                  </span>
                  {item.state ? (
                    <Badge variant={item.state.variant} className="flex items-center gap-1.5">
                      {item.state.busy ? <Loader2 size={12} className="animate-spin" aria-hidden /> : null}
                      {item.state.label}
                    </Badge>
                  ) : null}
                </button>
              </li>
            ))}
          </ul>
        </section>
      ))}
    </Card>
  );
}

// Deliverables for one engagement: first the list of the latest run's artifacts by kind, then the chosen one. A
// deck opens slide by slide for review; anything else shows a summary with a final approve or reject.
export default function EngagementDeliverablesPage() {
  const params = useParams();
  const router = useRouter();
  const { api } = useAuth();
  const id = typeof params.id === "string" ? params.id : Array.isArray(params.id) ? (params.id[0] ?? "") : "";

  const deliverables = useDeliverablesQuery(id);
  const readiness = useExportReadinessQuery(id);
  const engagement = useEngagementDetailQuery(id);
  const slideDecisions = useSlideDecisions(deliverables.data?.runId ?? "");
  // A run waiting in design review is answered per artifact: the deck's Accept PPT and Reject PPT, and the
  // Word draft's Approve and Reject.
  const deckReview = useDeckDesignReview(deliverables.data?.runId ?? "", deliverables.data?.pptx.slides.length ?? 0);
  const wordReview = useArtifactDesignReview(deliverables.data?.runId ?? "", WORD_REVIEW_TYPES);
  // When generation finishes, load the new drafts without a manual refresh.
  const latestRun = useRunProgressQuery(id).data?.run;
  const finishedRun = latestRun?.finished ? latestRun.id : "";
  const refetchDeliverables = deliverables.refetch;
  useEffect(() => {
    if (finishedRun) void refetchDeliverables();
  }, [finishedRun, refetchDeliverables]);
  // Load the rebuilt artifact once a regenerated version is ready.
  const readyVersions = [deckReview, wordReview].map((r) => (r && !r.regenerating ? r.version : "")).join("|");
  useEffect(() => {
    if (readyVersions !== "|") void refetchDeliverables();
  }, [readyVersions, refetchDeliverables]);
  const [view, setView] = useState<DeliverableView>("list");
  const [slideIndex, setSlideIndex] = useState(0);
  const [downloadError, setDownloadError] = useState<unknown>(null);

  // Links such as ?tab=powerpoint (from the engagement's Deliverables tab) open that artifact.
  useEffect(() => {
    const requested = new URLSearchParams(window.location.search).get("tab") as DeliverableView | null;
    // eslint-disable-next-line react-hooks/set-state-in-effect -- reading the URL once on mount
    if (requested && VIEWS.includes(requested)) setView(requested);
  }, []);

  if (deliverables.isPending) return <PageSkeleton />;

  const engagementName = deliverables.data?.engagementName ?? engagement.data?.name ?? "Engagement";
  const breadcrumb = (
    <>
      <Link href={`/engagements/${id}`}>{engagementName}</Link> / Deliverables{VIEW_CRUMB[view]}
    </>
  );

  if (deliverables.isError || !deliverables.data) {
    return (
      <PageFrame back={<BackButton href="/deliverables" label="Back to deliverables" />} breadcrumb={breadcrumb} title="Deliverables & artifacts">
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
  // A download unlocks once its artifact is approved, or for drafts approved in an earlier review.
  const canDownload = (kind: ArtifactKind) =>
    Boolean((kind === "pptx" ? deckReview : wordReview)?.approved) || reviewOf(kind)?.export === "Available";
  const hasPptx = data.tabCounts.powerpoint > 0;
  const hasDocx = data.tabCounts.word > 0;
  const pptxVersion = pptx.versionLabel.split(" ").pop() ?? "";
  const docxVersion = docx.versionLabel.split(" ").pop() ?? "";
  const unsupported = data.claims.filter((c) => !c.grounded).length;
  const supported = data.claims.length - unsupported;
  const slideLinks = data.claimsBySlideIndex[slideIndex] ?? [];

  const groups = [
    {
      title: "Presentations",
      items: hasPptx
        ? [
            {
              view: "powerpoint" as const,
              name: pptx.name,
              meta: `PowerPoint · ${pptx.slides.length} slides · ${deckReview?.version ?? pptxVersion}`,
              state: reviewState(deckReview),
            },
          ]
        : [],
    },
    {
      title: "Documents",
      items: hasDocx
        ? [
            {
              view: "word" as const,
              name: docx.name,
              meta: `Word · ${docx.preview.sections.length} sections · ${wordReview?.version ?? docxVersion}`,
              state: reviewState(wordReview),
            },
          ]
        : [],
    },
    {
      title: "Supporting evidence",
      items: data.claims.length
        ? [{ view: "evidence-register" as const, name: "Evidence register", meta: `${data.claims.length} claims · ${supported} supported` }]
        : [],
    },
  ].filter((group) => group.items.length > 0);

  const getSlideDetail = (index: number) =>
    toSlideDetail(data.rawSlides[index], index, data.rawSlides.length, data.slideBreadcrumb, data.slideSourcesSummary, data.slideFooterMeta);
  // While the deck regenerates, its rebuilt slides (every slide, for a whole rebuild) show as in progress.
  const slideRebuilding = (slideNumber: number) =>
    Boolean(deckReview?.regenerating) &&
    (deckReview!.rebuildingSlides.length === 0 || deckReview!.rebuildingSlides.includes(slideNumber));
  const claimCounts = Object.fromEntries(Object.entries(data.claimsBySlideIndex).map(([i, links]) => [i, links.length]));
  const slideReview: SlideReview = {
    decisionOf: slideDecisions.decisionOf,
    onDecide: slideDecisions.decide,
    onDecideAll: slideDecisions.decideAll,
    locked: pptxReview?.review === "Approved" || Boolean(deckReview?.approved),
    designReview: deckReview,
  };

  async function download(kind: ArtifactKind) {
    setDownloadError(null);
    try {
      await downloadFile(api, `/api/runs/${id}/${runId}/artifacts/${kind}/download`, `${data.engagementName}.${kind}`);
    } catch (err) {
      setDownloadError(err);
    }
  }

  // How to unlock a locked download.
  const exportNotice = (kind: ArtifactKind) =>
    canDownload(kind) ? null : (
      <ExportApprovalNotice
        description={
          kind === "pptx"
            ? "Review the slides, then use Accept PPT to unlock the PPTX download."
            : "Approve the document to unlock the DOCX download."
        }
      />
    );

  const header: Record<DeliverableView, { title: string; subtitle: string }> = {
    list: { title: data.title, subtitle: data.subtitle },
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
    view === "list" ? (
      <Button type="button" className="flex items-center gap-2" onClick={() => router.push(`/engagements/${id}/conversation`)}>
        <Plus size={16} aria-hidden />
        Create deliverable
      </Button>
    ) : null;

  const empty = (what: string) => <EmptyState title="Nothing here yet" description={`This run did not produce ${what}.`} />;

  // An artifact steps back to the artifact list; from there, to the engagements' deliverables.
  const back =
    view !== "list" ? (
      <BackButton onClick={() => setView("list")} label="Back to all artifacts" />
    ) : (
      <BackButton href="/deliverables" label="Back to deliverables" />
    );

  return (
    <PageFrame back={back} breadcrumb={breadcrumb} title={header[view].title} subtitle={header[view].subtitle} actions={actions}>
      <RunProgressCard pid={id} showArtifactsLink={false} />
      {data.fromEarlierRun ? (
        <p className="text-sm text-[var(--text-muted)]">
          The latest run produced no drafts, so these are from the run of {formatRunTime(data.run.createdAt)}.
        </p>
      ) : null}

      <ErrorNote error={downloadError} />

      {view === "list" ? (
        <div className="grid gap-4 lg:grid-cols-[1fr_280px]">
          {groups.length ? <ArtifactList groups={groups} onOpen={setView} /> : empty("any artifacts")}
          <VersionHistoryPanel versions={data.versions} />
        </div>
      ) : null}

      {view === "powerpoint" ? (
        hasPptx ? (
          <>
            {deckReview?.regenerating ? (
              <RegeneratingNotice
                label="deck"
                version={deckReview.version}
                rebuildingSlides={deckReview.rebuildingSlides}
                totalSlides={pptx.slides.length}
              />
            ) : null}
            <div className="grid gap-4 lg:grid-cols-[260px_1fr]">
              <SlideNavigator
                slides={pptx.slides}
                activeIndex={slideIndex}
                claimCounts={claimCounts}
                onSelect={setSlideIndex}
                decisionOf={slideReview.decisionOf}
              />
              <Card className="space-y-4">
                <div className="flex flex-wrap items-baseline gap-2">
                  <h2 className="text-base font-semibold text-[var(--text-default)]">{pptx.name}</h2>
                  <span className="text-xs text-[var(--text-muted)]">
                    · Slide {slideIndex + 1} / {pptx.slides.length}
                  </span>
                </div>
                <div className="relative">
                  <SlideCanvas slide={getSlideDetail(slideIndex)} />
                  {slideRebuilding(slideIndex + 1) ? <RegeneratingSlideOverlay /> : null}
                </div>
                <SlideReviewBar index={slideIndex} total={pptx.slides.length} onSelect={setSlideIndex} review={slideReview} />
                <div className="flex flex-wrap justify-end gap-2">
                  <Button
                    variant="secondary"
                    type="button"
                    disabled={!canDownload("pptx")}
                    title={canDownload("pptx") ? undefined : "Available after the deck is accepted"}
                    className="flex items-center gap-2"
                    onClick={() => void download("pptx")}
                  >
                    <Download size={16} aria-hidden />
                    Download PPTX
                  </Button>
                </div>
                <DeckDecisionButtons slides={pptx.slides} review={slideReview} />
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
            {exportNotice("pptx")}
          </>
        ) : (
          empty("a deck")
        )
      ) : null}

      {view === "word" ? (
        hasDocx ? (
          <>
            {wordReview?.regenerating ? <RegeneratingNotice label="document" version={wordReview.version} /> : null}
            <Card className="space-y-4">
              <div className="flex flex-wrap items-baseline justify-between gap-2">
                <h2 className="text-base font-semibold text-[var(--text-default)]">{docx.name}</h2>
                <span className="text-xs text-[var(--text-muted)]">
                  Word · {wordReview?.version ?? docxVersion} · {docx.citationSummary}
                </span>
              </div>
              <div className="space-y-1.5">
                <p className="text-2xs font-semibold uppercase tracking-wide text-[var(--text-muted)]">Summary</p>
                <p className="text-sm text-[var(--text-default)]">
                  {docx.preview.sections.length} section{docx.preview.sections.length === 1 ? "" : "s"}
                  {data.claims.length ? ` · ${supported} of ${data.claims.length} claims supported by a source` : ""}.
                </p>
                <ol className="list-decimal space-y-0.5 pl-5 text-sm text-[var(--text-default)]">
                  {docx.preview.sections.map((section, i) => (
                    <li key={`${section.heading}-${i}`}>{section.heading}</li>
                  ))}
                </ol>
              </div>
              {unsupported ? (
                <div className="rounded-lg border border-[#F3E2C0] bg-[#FCF3E2] p-3">
                  <p className="text-sm font-semibold text-[#8C5B12]">Assumptions to caveat</p>
                  <p className="text-xs text-[#8C5B12]">
                    {unsupported} claim{unsupported === 1 ? " has" : "s have"} no validated source; see the evidence register.
                  </p>
                </div>
              ) : null}
              <div className="flex justify-end">
                <Button
                  variant="secondary"
                  type="button"
                  disabled={!canDownload("docx")}
                  title={canDownload("docx") ? undefined : "Available after the document is approved"}
                  className="flex items-center gap-2"
                  onClick={() => void download("docx")}
                >
                  <Download size={16} aria-hidden />
                  Download DOCX
                </Button>
              </div>
              <ArtifactApproval label="Document" design={wordReview} />
            </Card>
            {exportNotice("docx")}
          </>
        ) : (
          empty("a document")
        )
      ) : null}

      {view === "evidence-register" ? (
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
