"use client";

import { Upload } from "lucide-react";
import { type ReactNode, useEffect, useState } from "react";

import {
  ApprovePublishTab,
  ExtractChunkTab,
  IndexValidateTab,
  IngestionJobPanel,
  LibraryApprovalControls,
  PipelineStepper,
  PracticeInventoryPanel,
  PublishControl,
  QualityGatesTab,
  QualityReviewPanel,
  RequestCorrectionModal,
  UploadSourcesModal,
} from "@/components/admin-console";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { ReasonAction } from "@/components/workbench/AdminControls";
import { ErrorNote, PageFrame, PageSkeleton } from "@/components/workbench/PageFrame";
import { type AdminLibrary, useAdminLibraryQuery } from "@/hooks/useAdminConsole";

// One view per ingestion pipeline step; the keys match the pipeline step ids, so the stepper navigates.
const TABS = [
  { key: "source-upload", label: "Source upload" },
  { key: "extract-chunk", label: "Extract & chunk" },
  { key: "index-validate", label: "Index & validate" },
  { key: "quality-review", label: "Quality review" },
  { key: "approve-publish", label: "Approve & publish" },
] as const;

type LibraryTab = (typeof TABS)[number]["key"];

const isLibraryTab = (value: string | null): value is LibraryTab => TABS.some((tab) => tab.key === value);

const BREADCRUMB = "Admin console / Leading practice library";

function MissingStep() {
  return <ErrorNote error={new Error("This pipeline step has no data. Upload a source to run the pipeline.")} />;
}

/** Keep the open step and the selected practice in the URL so the view can be linked and reloaded. */
function writeUrl(tab: LibraryTab, practice: string) {
  const url = new URL(window.location.href);
  if (tab === "source-upload") url.searchParams.delete("tab");
  else url.searchParams.set("tab", tab);
  if (practice) url.searchParams.set("practice", practice);
  else url.searchParams.delete("practice");
  window.history.replaceState(null, "", url);
}

export default function AdminConsoleLibraryPage() {
  const [practice, setPractice] = useState("");
  const library = useAdminLibraryQuery(practice);
  const [tab, setTab] = useState<LibraryTab>("source-upload");
  const [upload, setUpload] = useState<{ correction: boolean } | null>(null);
  const [uploadMessage, setUploadMessage] = useState<string | null>(null);
  const [correctionOpen, setCorrectionOpen] = useState(false);
  const [correctionSent, setCorrectionSent] = useState<string | null>(null);

  // Read the step and practice from the URL after mount, as the user library does for ?practice=.
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const requested = params.get("tab");
    if (isLibraryTab(requested)) setTab(requested);
    setPractice(params.get("practice") ?? "");
  }, []);

  function openTab(next: LibraryTab) {
    setTab(next);
    writeUrl(next, practice);
    window.scrollTo({ top: 0 });
  }

  function selectPractice(id: string) {
    setPractice(id);
    setCorrectionSent(null);
    writeUrl(tab, id);
  }

  if (library.isPending) return <PageSkeleton />;
  const data = library.data;
  if (!data) {
    return (
      <PageFrame breadcrumb={BREADCRUMB} title="Library management">
        <ErrorNote error={library.error} />
      </PageFrame>
    );
  }

  const uploaded = data.pipelineSource === "upload";
  const practiceId = data.qualityGates?.practiceId ?? data.qualityReview.id;
  const quality = data.qualityGates;
  const selectedTitle = data.practiceInventory.find((row) => row.id === practiceId)?.practiceSource.split(" · ")[0];
  const tabLabel = TABS.find((item) => item.key === tab)?.label ?? "";

  const sampleNote =
    !uploaded && tab !== "source-upload" ? (
      <p className="rounded-md border border-[var(--surface-border)] bg-[var(--surface-muted)] px-3 py-2 text-xs text-[var(--text-muted)]">
        Sample walkthrough ·{" "}
        {practice ? `${practice.toUpperCase()} has no uploaded source.` : "No sources have been uploaded yet."} Upload a PDF, Word,
        PowerPoint or Excel source to run these steps on real content.
      </p>
    ) : null;

  const frame = (title: string, subtitle: ReactNode, content: ReactNode, actions?: ReactNode) => (
    <PageFrame
      breadcrumb={tab === "source-upload" ? BREADCRUMB : `${BREADCRUMB} / ${tabLabel}`}
      title={title}
      subtitle={subtitle}
      actions={actions}
    >
      <PipelineStepper
        steps={data.pipelineSteps}
        activeId={tab}
        onSelect={(stepId) => {
          if (isLibraryTab(stepId)) openTab(stepId);
        }}
      />
      {sampleNote}
      {content}
    </PageFrame>
  );

  const modals = (
    <>
      {correctionOpen && quality ? (
        <RequestCorrectionModal
          practiceId={practiceId}
          draft={quality.correction}
          onClose={() => setCorrectionOpen(false)}
          onSent={setCorrectionSent}
        />
      ) : null}
      {upload ? (
        <UploadSourcesModal
          practice={
            upload.correction
              ? { id: practiceId, title: selectedTitle ?? practiceId.toUpperCase(), owner: quality?.correction.assignee }
              : undefined
          }
          onClose={() => setUpload(null)}
          onUploaded={(jobs) => {
            setUpload(null);
            setCorrectionSent(null);
            const first = jobs[0];
            setUploadMessage(
              jobs.length === 1
                ? `${first.id} · ${first.practiceId.toUpperCase()}: ${first.outcome}.`
                : `${jobs.length} sources uploaded: ${jobs.map((job) => `${job.id} (${job.outcome})`).join(", ")}.`,
            );
            if (first) {
              setPractice(first.practiceId);
              setTab("extract-chunk");
              writeUrl("extract-chunk", first.practiceId);
            }
          }}
        />
      ) : null}
    </>
  );
  const uploadButton = (
    <Button type="button" className="flex items-center gap-2 text-xs font-semibold" onClick={() => setUpload({ correction: false })}>
      <Upload size={14} aria-hidden />
      Upload sources
    </Button>
  );
  const message = uploadMessage ? (
    <p role="status" className="text-sm text-[var(--accent-green-dark)]">
      {uploadMessage}
    </p>
  ) : null;

  switch (tab) {
    case "extract-chunk":
      return frame(
        "Extract & chunk",
        data.extraction?.subtitle,
        <>
          {message}
          {data.extraction ? <ExtractChunkTab extraction={data.extraction} onContinue={() => openTab("index-validate")} /> : <MissingStep />}
        </>,
      );

    case "index-validate":
      return frame(
        "Index & validate",
        data.indexValidation?.subtitle,
        data.indexValidation ? (
          <IndexValidateTab validation={data.indexValidation} onContinue={() => openTab("quality-review")} />
        ) : (
          <MissingStep />
        ),
      );

    case "quality-review":
      return frame(
        quality?.title ?? `Quality review: ${data.qualityReview.title}`,
        quality?.subtitle,
        <>
          {quality ? (
            <QualityGatesTab
              quality={quality}
              correctionSent={correctionSent}
              onRequestCorrection={() => setCorrectionOpen(true)}
              onUploadCorrection={uploaded ? () => setUpload({ correction: true }) : undefined}
              publishAction={
                uploaded ? (
                  <LibraryApprovalControls practiceId={practiceId} quality={quality} />
                ) : quality.blocker ? (
                  <Button type="button" disabled title="Publication is blocked until the correction is reviewed.">
                    Approve &amp; publish
                  </Button>
                ) : (
                  <ReasonAction
                    primary
                    label="Approve & publish"
                    build={(reason) => ({ path: `/library/${practiceId}/publish`, body: { reason } })}
                  />
                )
              }
            />
          ) : (
            <MissingStep />
          )}
          {modals}
        </>,
      );

    case "approve-publish":
      return frame(
        data.release?.published === false ? "Approve & publish" : "Approve & publish practice",
        data.release?.subtitle,
        data.release ? (
          <ApprovePublishTab
            release={data.release}
            publishAction={
              <PublishControl
                practiceId={practiceId}
                canPublish={Boolean(data.release.canPublish)}
                blockers={data.release.blockers ?? []}
              />
            }
          />
        ) : (
          <MissingStep />
        ),
      );

    default:
      return frame(
        "Library management",
        "Ingest, verify and publish versioned practices. Only approved releases are available for user retrieval.",
        <>
          {message}
          <SourceUploadTab
            data={data}
            selectedId={practice || data.selectedPracticeId}
            onSelect={selectPractice}
            onRequestCorrection={quality ? () => setCorrectionOpen(true) : undefined}
            onOpenQualityReview={uploaded ? () => openTab("quality-review") : undefined}
          />
          {modals}
        </>,
        uploadButton,
      );
  }
}

/** Practice inventory and the latest ingestion job, beside the selected practice's review panel. */
function SourceUploadTab({
  data,
  selectedId,
  onSelect,
  onRequestCorrection,
  onOpenQualityReview,
}: {
  data: AdminLibrary;
  selectedId: string;
  onSelect: (id: string) => void;
  onRequestCorrection?: () => void;
  /** Uploaded practices are approved and published from the Quality review step. */
  onOpenQualityReview?: () => void;
}) {
  const reviewed = data.qualityReview;
  const selectedRow = data.practiceInventory.find((row) => row.id === selectedId);
  const compact = "px-4 py-2 text-xs font-semibold";

  return (
    <div className="grid grid-cols-1 gap-5 lg:grid-cols-[minmax(0,1fr)_440px]">
      <div className="space-y-5">
        <PracticeInventoryPanel rows={data.practiceInventory} activeId={selectedId} onSelect={onSelect} />
        <IngestionJobPanel job={data.latestIngestionJob} />
      </div>

      {selectedId === reviewed.id ? (
        <QualityReviewPanel
          review={reviewed}
          actions={
            <div className="flex flex-wrap items-start gap-2">
              {onRequestCorrection ? (
                <Button
                  type="button"
                  variant="secondary"
                  className={`${compact} whitespace-nowrap border border-[var(--surface-border-strong)]`}
                  onClick={onRequestCorrection}
                >
                  Request correction
                </Button>
              ) : null}
              {onOpenQualityReview ? (
                <Button type="button" className={`${compact} whitespace-nowrap`} onClick={onOpenQualityReview}>
                  Open quality review
                </Button>
              ) : (
                <ReasonAction
                  primary
                  label="Approve & publish"
                  disabled={Boolean(reviewed.warning)}
                  hint="Publication is blocked until the correction is reviewed."
                  className={`${compact} disabled:bg-[var(--surface-muted)] disabled:text-[var(--text-muted)] disabled:opacity-100`}
                  build={(reason) => ({ path: `/library/${reviewed.id}/publish`, body: { reason } })}
                />
              )}
            </div>
          }
        />
      ) : (
        <Card className="space-y-3">
          <h2 className="text-sm font-semibold text-[var(--text-default)]">{selectedRow?.practiceSource}</h2>
          <p className="text-xs text-[var(--text-muted)]">
            {selectedRow?.version} · {selectedRow?.indexing} · {selectedRow?.lifecycle}
          </p>
          <p className="text-xs text-[var(--text-default)]">
            {selectedRow?.lifecycle === "Approved"
              ? "Published in the Leading Practice Library. Upload a new version to start a candidate review."
              : "No uploaded source is in review for this practice. Publication follows its independent review."}
          </p>
          {selectedRow && selectedRow.lifecycle !== "Approved" ? (
            <ReasonAction
              primary
              label="Approve & publish"
              className={compact}
              build={(reason) => ({ path: `/library/${selectedRow.id}/publish`, body: { reason } })}
            />
          ) : null}
        </Card>
      )}
    </div>
  );
}
