"use client";

import { ArrowRight, Upload } from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";
import { type ReactNode, Suspense, useState } from "react";

import {
  ApprovePublishTab,
  DeletePracticeButton,
  ExtractChunkTab,
  INITIAL_PRACTICE_LIST,
  IndexValidateTab,
  IngestionJobPanel,
  LibraryBadge,
  LibraryUploadsPanel,
  PipelineStepper,
  PracticeInventoryPanel,
  type PracticeListState,
  PublishControl,
  QualityGatesTab,
  QualityReviewPanel,
  RequestCorrectionModal,
  SourceFilePanel,
  StepperFooter,
  StoredDataPanel,
  UploadProgressPanel,
  UploadSourcesModal,
} from "@/components/admin-console";
import { EngagementTabs } from "@/components/engagements/EngagementTabs";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { BackButton } from "@/components/workbench/BackButton";
import { ErrorNote, Field, PageFrame, PageSkeleton } from "@/components/workbench/PageFrame";
import { type LibraryUploadJob, queuedJobIds, useAdminLibraryQuery } from "@/hooks/useAdminConsole";

// One view per ingestion pipeline step; the keys match the pipeline step ids, so the stepper navigates.
const STEPS = [
  { key: "source-upload", label: "Source upload" },
  { key: "extract-chunk", label: "Extract & chunk" },
  { key: "index-validate", label: "Index & validate" },
  { key: "quality-review", label: "Quality review" },
  { key: "approve-publish", label: "Approve & publish" },
] as const;

type LibraryStep = (typeof STEPS)[number]["key"];

const isLibraryStep = (value: string | null): value is LibraryStep => STEPS.some((step) => step.key === value);

const BREADCRUMB = "Admin console / Leading practice library";
const SUBTITLE = "Ingest, verify and publish versioned practices. Only approved releases are available for user retrieval.";

const LIST_TABS = [
  { key: "practices", label: "Practices" },
  { key: "uploads", label: "Uploads" },
] as const;

type ListTab = (typeof LIST_TABS)[number]["key"];

/** The list, one practice, or one pipeline step of a practice. Every level is a URL, so back and reload work. */
function libraryHref(practice = "", step?: LibraryStep) {
  const params = new URLSearchParams();
  if (practice) params.set("practice", practice);
  if (step) params.set("tab", step);
  const query = params.toString();
  return `/admin/console/library${query ? `?${query}` : ""}`;
}

function MissingStep() {
  return <ErrorNote error={new Error("This pipeline step has no data. Upload a source to run the pipeline.")} />;
}

/** "JOB-12 · LP-041: Queued for extraction"; before intake has run the file name stands in for the job. */
function uploadSummary(job: LibraryUploadJob) {
  const label = job.id ? `${job.id} · ${job.practiceId.toUpperCase()}` : (job.ingestion?.filename ?? "Source");
  return `${label}: ${job.outcome}`;
}

type UploadTarget = { id: string; title: string; owner?: string; heading?: string };

export default function AdminConsoleLibraryPage() {
  return (
    <Suspense fallback={<PageSkeleton />}>
      <LibraryScreen />
    </Suspense>
  );
}

function LibraryScreen() {
  const router = useRouter();
  const params = useSearchParams();
  const practice = (params.get("practice") ?? "").trim().toLowerCase();
  const requestedStep = params.get("tab");
  const library = useAdminLibraryQuery(practice);

  const [listTab, setListTab] = useState<ListTab>("practices");
  const [listState, setListState] = useState<PracticeListState>(INITIAL_PRACTICE_LIST);
  const [upload, setUpload] = useState<{ practice?: UploadTarget } | null>(null);
  const [uploadMessage, setUploadMessage] = useState<string | null>(null);
  // Ingestion jobs of the latest upload, followed live until each one finishes.
  const [uploadJobIds, setUploadJobIds] = useState<string[]>([]);
  const [correctionOpen, setCorrectionOpen] = useState(false);
  const [correctionSent, setCorrectionSent] = useState<{ practice: string; id: string } | null>(null);

  // Opening a practice keeps the previous one's data up while it loads; never show (or act on) that as this practice.
  if (library.isPending || (practice && library.isPlaceholderData)) return <PageSkeleton />;
  const data = library.data;
  if (!data) {
    return (
      <PageFrame breadcrumb={BREADCRUMB} title="Library management">
        <ErrorNote error={library.error} />
      </PageFrame>
    );
  }

  const uploadButton = (label = "Upload sources", target?: UploadTarget, secondary = false) => (
    <Button
      type="button"
      variant={secondary ? "secondary" : undefined}
      className="flex items-center gap-2 whitespace-nowrap text-sm"
      onClick={() => setUpload({ practice: target })}
    >
      <Upload size={16} aria-hidden />
      {label}
    </Button>
  );

  const message = (
    <>
      {uploadMessage ? (
        <p role="status" className="text-sm text-[var(--accent-green-dark)]">
          {uploadMessage}
        </p>
      ) : null}
      <UploadProgressPanel
        jobIds={uploadJobIds}
        onOpenPractice={(id) => router.push(libraryHref(id, "extract-chunk"))}
        onDismiss={() => {
          setUploadJobIds([]);
          setUploadMessage(null);
        }}
      />
    </>
  );

  const uploadModal = upload ? (
    <UploadSourcesModal
      practice={upload.practice}
      onClose={() => setUpload(null)}
      onUploaded={(jobs) => {
        const first = jobs[0];
        setUpload(null);
        setCorrectionSent(null);
        setUploadMessage(jobs.length === 1 ? `${uploadSummary(first)}.` : `${jobs.length} sources uploaded: ${jobs.map(uploadSummary).join("; ")}.`);
        setUploadJobIds(queuedJobIds(jobs));
        // One source opens where its pipeline runs; several stay on the list, each linked from its progress row.
        // Intake may still be running, in which case the progress panel links to the practice once it exists.
        if (jobs.length === 1 && first?.practiceId) router.push(libraryHref(first.practiceId, "extract-chunk"));
      }}
    />
  ) : null;

  // ---- Level 1: the list of practices.
  if (!practice) {
    return (
      <PageFrame breadcrumb={BREADCRUMB} title="Library management" subtitle={SUBTITLE} actions={uploadButton()}>
        {message}
        <EngagementTabs tabs={[...LIST_TABS]} active={listTab} onChange={setListTab} />
        {listTab === "practices" ? (
          <PracticeInventoryPanel rows={data.practiceInventory} state={listState} onChange={setListState} hrefFor={(id) => libraryHref(id)} />
        ) : (
          <div className="space-y-5">
            {data.pipelineSource === "upload" ? <IngestionJobPanel job={data.latestIngestionJob} /> : null}
            <LibraryUploadsPanel activeId="" onSelect={(id) => router.push(libraryHref(id))} />
          </div>
        )}
        {uploadModal}
      </PageFrame>
    );
  }

  const listBack = <BackButton href={libraryHref()} label="Back to Library management" />;
  const row = data.practiceInventory.find((item) => item.id === practice);
  const code = practice.toUpperCase();

  if (!row) {
    return (
      <PageFrame back={listBack} breadcrumb={BREADCRUMB} title={code}>
        <ErrorNote error={new Error(`${code} is not in the library. It may have been deleted.`)} />
      </PageFrame>
    );
  }

  const title = row.practiceSource.split(" · ")[0];
  const onDeleted = (deletedMessage: string) => {
    setUploadMessage(deletedMessage);
    router.push(libraryHref());
  };
  const deleteAction = <DeletePracticeButton key={row.id} practiceId={row.id} className="px-4 py-2 text-xs font-semibold" onDeleted={onDeleted} />;
  // The API falls back to a sample walkthrough for a practice with no upload; that data is not this practice's.
  const uploaded = data.pipelineSource === "upload" && data.selectedPracticeId === practice;

  // ---- Level 2 without a pipeline: a practice that never came through upload.
  if (!uploaded) {
    const published = row.lifecycle === "Approved";
    return (
      <PageFrame
        back={listBack}
        breadcrumb={`${BREADCRUMB} / ${code}`}
        title={title}
        subtitle={`${code} · ${row.version}`}
        actions={uploadButton("Upload new version", { id: row.id, title, heading: "Upload new version" }, !published)}
      >
        {message}
        <Card className="max-w-2xl space-y-4">
          <div className="grid gap-4 sm:grid-cols-3">
            <Field label="Version">{row.version}</Field>
            <Field label="Indexing">
              <LibraryBadge>{row.indexing}</LibraryBadge>
            </Field>
            <Field label="Lifecycle">
              <LibraryBadge>{published ? "Published" : row.lifecycle}</LibraryBadge>
            </Field>
          </div>
          <p className="text-sm text-[var(--text-default)]">
            {published
              ? "Published in the Leading Practice Library. Upload a new version to start a candidate review."
              : "No uploaded source is in review for this practice. Publishing records you as its approver."}
          </p>
          <div className="flex flex-wrap items-start gap-2 border-t border-[var(--surface-border)] pt-4">
            {!published ? <PublishControl practiceId={row.id} canPublish blockers={[]} /> : null}
            {deleteAction}
          </div>
        </Card>
        {uploadModal}
      </PageFrame>
    );
  }

  const quality = data.qualityGates;
  const review = data.qualityReview;
  const steps = data.pipelineSteps;
  const correctionId = correctionSent?.practice === practice ? correctionSent.id : null;
  const correctionTarget: UploadTarget = { id: practice, title, owner: quality?.correction.assignee };
  const newVersionTarget: UploadTarget = review.approvalState === "Published" ? { ...correctionTarget, heading: "Upload new version" } : correctionTarget;
  const correctionModal =
    correctionOpen && quality ? (
      <RequestCorrectionModal
        practiceId={practice}
        draft={quality.correction}
        onClose={() => setCorrectionOpen(false)}
        onSent={(id) => setCorrectionSent({ practice, id })}
      />
    ) : null;
  const openStep = (stepId: string) => {
    if (isLibraryStep(stepId)) router.push(libraryHref(practice, stepId));
  };
  const stepIndex = STEPS.findIndex((step) => step.key === requestedStep);

  // ---- Level 2: the practice itself; its pipeline opens from here.
  if (stepIndex < 0) {
    const current = steps.find((step) => step.status === "in-progress");
    const published = review.approvalState === "Published";
    return (
      <PageFrame
        back={listBack}
        breadcrumb={`${BREADCRUMB} / ${review.code}`}
        title={review.title}
        subtitle={
          <span className="flex flex-wrap items-center gap-2">
            {review.code}
            <LibraryBadge tone="neutral">{review.versionLabel}</LibraryBadge>
            <LibraryBadge tone={published ? "success" : "warning"}>{review.approvalState}</LibraryBadge>
          </span>
        }
        actions={uploadButton(published ? "Upload new version" : "Upload corrected source", newVersionTarget, true)}
      >
        {message}
        <PipelineStepper steps={steps} activeId={current?.id ?? steps[steps.length - 1]?.id ?? ""} onSelect={openStep} />
        <div className="grid grid-cols-1 gap-5 lg:grid-cols-[minmax(0,1fr)_340px]">
          <QualityReviewPanel review={review} />
          <Card className="h-fit space-y-4">
            <div>
              <p className="text-2xs font-semibold uppercase tracking-wide text-[var(--text-muted)]">{current ? "Next step" : "Pipeline"}</p>
              <p className="mt-1 text-sm font-semibold text-[var(--text-default)]">{current?.label ?? "All steps complete"}</p>
              {current ? <p className="text-xs text-[var(--text-muted)]">{current.helper}</p> : null}
            </div>
            <Button
              type="button"
              className="flex w-full items-center justify-center gap-2 text-sm"
              onClick={() => openStep(current?.id ?? STEPS[0].key)}
            >
              {current ? `Continue to ${current.label}` : "View pipeline"}
              <ArrowRight size={16} aria-hidden />
            </Button>
            {quality && !published ? (
              <Button type="button" variant="secondary" className="w-full text-sm" onClick={() => setCorrectionOpen(true)}>
                {correctionId || quality.openCorrection ? "Update correction request" : "Request correction"}
              </Button>
            ) : null}
            <p className="text-2xs text-[var(--text-muted)]">{review.footnote}</p>
            <div className="border-t border-[var(--surface-border)] pt-4">{deleteAction}</div>
          </Card>
        </div>
        {correctionModal}
        {uploadModal}
      </PageFrame>
    );
  }

  // ---- Level 3: the pipeline stepper, one step at a time.
  const step = STEPS[stepIndex];
  const previous = STEPS[stepIndex - 1];
  const next = STEPS[stepIndex + 1];
  // The upload job behind the selected practice.
  const ingestionJobId = data.ingestion?.job_id;

  const stepView = (heading: string, subtitle: ReactNode, content: ReactNode) => (
    <PageFrame
      back={listBack}
      breadcrumb={`${BREADCRUMB} / ${review.code} / ${step.label}`}
      title={heading}
      subtitle={subtitle}
    >
      <PipelineStepper steps={steps} activeId={step.key} onSelect={openStep} />
      {message}
      {content}
      <StepperFooter
        position={stepIndex + 1}
        total={STEPS.length}
        backLabel={previous ? `Previous: ${previous.label}` : "Back to practice"}
        onBack={() => router.push(libraryHref(practice, previous?.key))}
        // "Next:" keeps this apart from the step's own actions; the Approve & publish button in a panel really publishes.
        nextLabel={next ? `Next: ${next.label}` : "Back to practice"}
        onNext={() => router.push(libraryHref(practice, next?.key))}
      />
      {correctionModal}
      {uploadModal}
    </PageFrame>
  );

  switch (step.key) {
    case "extract-chunk":
      return stepView(
        step.label,
        data.extraction?.subtitle,
        <>
          {data.extraction ? <ExtractChunkTab extraction={data.extraction} /> : <MissingStep />}
          {ingestionJobId ? <StoredDataPanel jobId={ingestionJobId} /> : null}
        </>,
      );

    case "index-validate":
      return stepView(
        step.label,
        data.indexValidation?.subtitle,
        data.indexValidation ? <IndexValidateTab validation={data.indexValidation} /> : <MissingStep />,
      );

    case "quality-review":
      return stepView(
        quality?.title ?? step.label,
        quality?.subtitle,
        quality ? (
          <QualityGatesTab
            quality={quality}
            correctionSent={correctionId}
            onRequestCorrection={() => setCorrectionOpen(true)}
            onUploadCorrection={() => setUpload({ practice: correctionTarget })}
          />
        ) : (
          <MissingStep />
        ),
      );

    case "approve-publish":
      return stepView(
        step.label,
        data.release?.subtitle,
        data.release ? (
          <ApprovePublishTab
            release={data.release}
            publishAction={
              <PublishControl practiceId={practice} canPublish={Boolean(data.release.canPublish)} blockers={data.release.blockers ?? []} />
            }
          />
        ) : (
          <MissingStep />
        ),
      );

    default:
      return stepView(
        step.label,
        data.extraction?.subtitle,
        <SourceFilePanel
          job={data.ingestion}
          action={uploadButton(review.approvalState === "Published" ? "Upload new version" : "Upload corrected source", newVersionTarget, true)}
        />,
      );
  }
}
