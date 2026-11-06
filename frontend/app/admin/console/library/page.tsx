"use client";

import { Plus, Upload } from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";
import { type ReactNode, Suspense, useState } from "react";

import {
  ApprovePublishTab,
  DeletePracticeButton,
  ExtractChunkTab,
  INITIAL_PRACTICE_LIST,
  IndexValidateTab,
  PipelineStepper,
  PracticeDetailsCard,
  PracticeDetailsForm,
  PracticeInventoryPanel,
  type PracticeListState,
  PracticeSourcesPanel,
  PublishControl,
  QualityGatesTab,
  RequestCorrectionModal,
  SourceFilePanel,
  SourceUploadForm,
  StepperFooter,
  StoredDataPanel,
  UploadProgressPanel,
  type UploadTarget,
  stageLabel,
} from "@/components/admin-console";
import { Button } from "@/components/ui/Button";
import { BackButton } from "@/components/workbench/BackButton";
import { ErrorNote, PageFrame, PageSkeleton } from "@/components/workbench/PageFrame";
import { type LibraryUploadJob, queuedJobIds, useAdminLibraryQuery, useCreatePractice } from "@/hooks/useAdminConsole";
import { EMPTY_PRACTICE, type PracticeDetails } from "@/lib/libraryPractices";
import type { EngagementStep, LibrarySource } from "@/types/api";

// One view per ingestion pipeline step of a source; the keys match the pipeline step ids, so the stepper navigates.
const STEPS = [
  { key: "source-upload", label: "Source upload" },
  { key: "extract-chunk", label: "Extract & chunk" },
  { key: "index-validate", label: "Index & validate" },
  { key: "quality-review", label: "Quality review" },
  { key: "approve-publish", label: "Approve & publish" },
] as const;

type LibraryStep = (typeof STEPS)[number]["key"];

const isLibraryStep = (value: string | null): value is LibraryStep => STEPS.some((step) => step.key === value);

/** Before a source is uploaded, only its first step is open. */
const UPLOAD_ONLY_STEPS: EngagementStep[] = STEPS.map((step, index) => ({
  id: step.key,
  index: index + 1,
  label: step.label,
  status: index === 0 ? "in-progress" : "upcoming",
  helper: index === 0 ? "Choose a file" : "After upload",
}));

/** `source` value of a source that is being added, not yet uploaded. */
const NEW_SOURCE = "new";

const BREADCRUMB = "Admin console / Leading practice library";
const SUBTITLE = "Create practices, upload their sources, then verify and publish them. Only approved releases are available for user retrieval.";

/**
 * Every level is a URL, so back and reload work: the list, Create practice, a practice, and one pipeline step of one
 * of its sources.
 */
function libraryHref({ practice = "", source = "", step, create = false }: { practice?: string; source?: string; step?: LibraryStep; create?: boolean } = {}) {
  const params = new URLSearchParams();
  if (create) params.set("create", "1");
  if (practice) params.set("practice", practice);
  if (source) params.set("source", source);
  if (step) params.set("tab", step);
  const query = params.toString();
  return `/admin/console/library${query ? `?${query}` : ""}`;
}

function MissingStep() {
  return <ErrorNote error={new Error("This pipeline step has no data yet. Upload the source to run the pipeline.")} />;
}

/** "JOB-12 · LP-041: Queued for extraction"; before intake has run the file name stands in for the job. */
function uploadSummary(job: LibraryUploadJob) {
  const label = job.id ? `${job.id} · ${job.practiceId.toUpperCase()}` : (job.ingestion?.filename ?? "Source");
  return `${label}: ${job.outcome}`;
}

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
  const creating = params.get("create") === "1";
  const practice = (params.get("practice") ?? "").trim().toLowerCase();
  const source = (params.get("source") ?? "").trim();
  const requestedStep = params.get("tab");
  const library = useAdminLibraryQuery(practice, source === NEW_SOURCE ? "" : source);
  const createPractice = useCreatePractice();

  const [listState, setListState] = useState<PracticeListState>(INITIAL_PRACTICE_LIST);
  const [uploadMessage, setUploadMessage] = useState<string | null>(null);
  // Ingestion jobs of the latest upload, followed live until each one finishes.
  const [uploadJobIds, setUploadJobIds] = useState<string[]>([]);
  const [correctionOpen, setCorrectionOpen] = useState(false);
  const [correctionSent, setCorrectionSent] = useState<{ practice: string; id: string } | null>(null);

  const listBack = <BackButton href={libraryHref()} label="Back to Library management" />;

  // ---- Create practice: its details on a screen of their own; sources are uploaded from the practice afterwards.
  if (creating) {
    return (
      <PageFrame
        back={listBack}
        breadcrumb={`${BREADCRUMB} / Create practice`}
        title="Create practice"
        subtitle="Enter the practice details. You upload its sources from the practice once it is created."
      >
        <ErrorNote error={createPractice.error} />
        <PracticeDetailsForm
          initial={EMPTY_PRACTICE}
          submitting={createPractice.isPending}
          onCancel={() => router.push(libraryHref())}
          onSubmit={(details) => {
            createPractice
              .mutateAsync({
                title: details.title,
                description: details.description,
                category: details.taxonomy,
                maturity: details.maturity,
                version: details.version,
                owner: details.owner,
                classification: details.classification,
                rights: details.rights,
              })
              .then((created) => router.replace(libraryHref({ practice: created.id })))
              // createPractice.error is shown above the form.
              .catch(() => undefined);
          }}
        />
      </PageFrame>
    );
  }

  const message = (
    <>
      {uploadMessage ? (
        <p role="status" className="text-sm text-[var(--accent-green-dark)]">
          {uploadMessage}
        </p>
      ) : null}
      <UploadProgressPanel
        jobIds={uploadJobIds}
        onOpenPractice={(id) => router.push(libraryHref({ practice: id }))}
        onDismiss={() => {
          setUploadJobIds([]);
          setUploadMessage(null);
        }}
      />
    </>
  );

  /** After an upload: one source opens where its pipeline runs; otherwise the practice (or the list) shows progress. */
  const afterUpload = (jobs: LibraryUploadJob[], fallback: string) => {
    const first = jobs[0];
    setCorrectionSent(null);
    setUploadMessage(jobs.length === 1 ? `${uploadSummary(first)}.` : `${jobs.length} sources uploaded: ${jobs.map(uploadSummary).join("; ")}.`);
    setUploadJobIds(queuedJobIds(jobs));
    if (jobs.length === 1 && first?.practiceId) {
      router.push(libraryHref({ practice: first.practiceId, source: first.sourceId || "SRC-1", step: "extract-chunk" }));
    } else {
      // Intake may still be running; the progress panel links to the practice once it exists.
      router.push(first?.practiceId ? libraryHref({ practice: first.practiceId }) : fallback);
    }
  };

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

  // ---- Level 1: the list of practices.
  if (!practice) {
    return (
      <PageFrame
        breadcrumb={BREADCRUMB}
        title="Library management"
        subtitle={SUBTITLE}
        actions={
          <Button type="button" className="flex items-center gap-2 whitespace-nowrap text-sm" onClick={() => router.push(libraryHref({ create: true }))}>
            <Plus size={16} aria-hidden />
            Create practice
          </Button>
        }
      >
        {message}
        <PracticeInventoryPanel
          rows={data.practiceInventory}
          state={listState}
          onChange={setListState}
          hrefFor={(id) => libraryHref({ practice: id })}
        />
      </PageFrame>
    );
  }

  const row = data.practiceInventory.find((item) => item.id === practice);
  const code = practice.toUpperCase();

  if (!row) {
    return (
      <PageFrame back={listBack} breadcrumb={BREADCRUMB} title={code}>
        <ErrorNote error={new Error(`${code} is not in the library. It may have been deleted.`)} />
      </PageFrame>
    );
  }

  // The API falls back to a sample walkthrough for a practice with no upload; that data is not this practice's.
  const uploaded = data.pipelineSource === "upload" && data.selectedPracticeId === practice && (!source || data.selectedSourceId === source);
  const review = data.qualityReview;
  const published = row.lifecycle === "Approved";
  const title = data.practice?.title ?? (uploaded ? review.title : row.practiceSource.split(" · ")[0]);
  const sources: LibrarySource[] = data.practice?.sources ?? [];
  const details: Partial<PracticeDetails> = data.practice
    ? {
        description: data.practice.description,
        taxonomy: data.practice.taxonomy,
        maturity: data.practice.maturity,
        version: data.practice.versionLabel,
        owner: data.practice.owner,
        classification: data.practice.classification,
        rights: data.practice.rights,
      }
    : uploaded
      ? { taxonomy: review.taxonomy, maturity: review.maturity, version: row.version, owner: review.practiceOwner, rights: review.sourceAttribution }
      : { version: row.version };
  const uploadDefaults = { owner: details.owner ?? "", classification: details.classification ?? "", rights: details.rights ?? "" };
  const onDeleted = (deletedMessage: string) => {
    setUploadMessage(deletedMessage);
    router.push(libraryHref());
  };
  const deleteAction = <DeletePracticeButton key={row.id} practiceId={row.id} className="px-4 py-2 text-xs font-semibold" onDeleted={onDeleted} />;
  const practiceHref = libraryHref({ practice });
  const practiceBack = <BackButton href={practiceHref} label={`Back to ${title}`} />;

  // ---- Level 2: the practice, its details and its sources; Upload source opens the stepper.
  if (!source) {
    return (
      <PracticeOverview
        back={listBack}
        code={code}
        title={title}
        details={details}
        status={published ? "Published" : row.lifecycle}
        sources={sources}
        message={message}
        onUpload={() => router.push(libraryHref({ practice, source: NEW_SOURCE, step: "source-upload" }))}
        onOpenSource={(id) => router.push(libraryHref({ practice, source: id }))}
        onNewVersion={(id) => router.push(libraryHref({ practice, source: id, step: "source-upload" }))}
        footer={
          <>
            {/* A practice that never came through upload can still be published as it stands; a new one needs a source first. */}
            {!published && sources.length === 0 && !uploaded && row.lifecycle !== "Draft" ? (
              <PublishControl practiceId={row.id} canPublish blockers={[]} />
            ) : null}
            {deleteAction}
          </>
        }
      />
    );
  }

  // ---- Level 3, new source: the stepper opens on Source upload; the other steps follow once a file is uploaded.
  if (source === NEW_SOURCE) {
    return (
      <PageFrame back={practiceBack} breadcrumb={`${BREADCRUMB} / ${code} / Upload source`} title="Source upload" subtitle={`${code} · ${title} · New source`}>
        <PipelineStepper steps={UPLOAD_ONLY_STEPS} activeId="source-upload" onSelect={() => undefined} />
        {message}
        <SourceUploadForm
          target={{ kind: "source", practiceId: practice, ...uploadDefaults }}
          maxFiles={10}
          onCancel={() => router.push(practiceHref)}
          onUploaded={(jobs) => afterUpload(jobs, practiceHref)}
        />
        <StepperFooter
          position={1}
          total={STEPS.length}
          backLabel="Back to practice"
          onBack={() => router.push(practiceHref)}
          nextLabel={`Next: ${STEPS[1].label}`}
          nextDisabled
          onNext={() => undefined}
        />
      </PageFrame>
    );
  }

  const sourceDetail = sources.find((item) => item.id === source);
  if (!uploaded || !sourceDetail) {
    return (
      <PageFrame back={practiceBack} breadcrumb={`${BREADCRUMB} / ${code}`} title={title}>
        <ErrorNote error={new Error(`${code} has no source ${source}. Open a source from the practice.`)} />
      </PageFrame>
    );
  }

  // ---- Level 3: the pipeline stepper of one source, one step at a time.
  const quality = data.qualityGates;
  const steps = data.pipelineSteps;
  const requestedIndex = STEPS.findIndex((step) => step.key === requestedStep);
  // Opening a source without a step lands on the step it has reached.
  const reached = steps.find((step) => step.status === "in-progress")?.id ?? steps[steps.length - 1]?.id;
  const stepIndex = requestedIndex >= 0 ? requestedIndex : Math.max(0, STEPS.findIndex((step) => step.key === reached));
  const step = STEPS[stepIndex];
  const previous = STEPS[stepIndex - 1];
  const next = STEPS[stepIndex + 1];
  const correctionId = correctionSent?.practice === practice ? correctionSent.id : null;
  const versionTarget: UploadTarget = { kind: "version", practiceId: practice, sourceId: source, sourceName: sourceDetail.name, ...uploadDefaults };
  const sourceHref = (key?: LibraryStep) => libraryHref({ practice, source, step: key });

  const stepView = (heading: string, subtitle: ReactNode, content: ReactNode) => (
    <PageFrame back={practiceBack} breadcrumb={`${BREADCRUMB} / ${code} / ${sourceDetail.name} / ${step.label}`} title={heading} subtitle={subtitle}>
      <PipelineStepper steps={steps} activeId={step.key} onSelect={(id) => isLibraryStep(id) && router.push(sourceHref(id))} />
      {message}
      {content}
      <StepperFooter
        position={stepIndex + 1}
        total={STEPS.length}
        backLabel={previous ? `Previous: ${previous.label}` : "Back to practice"}
        onBack={() => router.push(previous ? sourceHref(previous.key) : practiceHref)}
        // "Next:" keeps this apart from the step's own actions; the Approve & publish button in a panel really publishes.
        nextLabel={next ? `Next: ${next.label}` : "Back to practice"}
        onNext={() => router.push(next ? sourceHref(next.key) : practiceHref)}
      />
      {correctionOpen && quality ? (
        <RequestCorrectionModal
          practiceId={practice}
          sourceId={source}
          draft={quality.correction}
          onClose={() => setCorrectionOpen(false)}
          onSent={(id) => setCorrectionSent({ practice, id })}
        />
      ) : null}
    </PageFrame>
  );

  switch (step.key) {
    case "extract-chunk":
      return stepView(
        step.label,
        data.extraction?.subtitle,
        <>
          {data.extraction ? <ExtractChunkTab extraction={data.extraction} /> : <MissingStep />}
          {data.ingestion?.job_id ? <StoredDataPanel jobId={data.ingestion.job_id} /> : null}
        </>,
      );

    case "index-validate":
      return stepView(step.label, data.indexValidation?.subtitle, data.indexValidation ? <IndexValidateTab validation={data.indexValidation} /> : <MissingStep />);

    case "quality-review":
      return stepView(
        quality?.title ?? step.label,
        quality?.subtitle,
        quality ? (
          <QualityGatesTab
            quality={quality}
            correctionSent={correctionId}
            onRequestCorrection={() => setCorrectionOpen(true)}
            onUploadCorrection={() => router.push(sourceHref("source-upload"))}
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
              <PublishControl practiceId={practice} sourceId={source} canPublish={Boolean(data.release.canPublish)} blockers={data.release.blockers ?? []} />
            }
          />
        ) : (
          <MissingStep />
        ),
      );

    default:
      return stepView(
        step.label,
        `${sourceDetail.name} · Version ${sourceDetail.versions[0]?.number ?? 1}`,
        <>
          <SourceFilePanel job={data.ingestion} />
          <SourceUploadForm target={versionTarget} onUploaded={(jobs) => afterUpload(jobs, practiceHref)} />
        </>,
      );
  }
}

/** A practice: its details, its sources, and Upload source. */
function PracticeOverview({
  back,
  code,
  title,
  details,
  status,
  sources,
  message,
  footer,
  onUpload,
  onOpenSource,
  onNewVersion,
}: {
  back: ReactNode;
  code: string;
  title: string;
  details: Partial<PracticeDetails>;
  status: string;
  sources: LibrarySource[];
  message: ReactNode;
  footer?: ReactNode;
  onUpload: () => void;
  onOpenSource: (sourceId: string) => void;
  onNewVersion: (sourceId: string) => void;
}) {
  const statusText = status === "Approved" ? "Published" : status;
  return (
    <PageFrame
      back={back}
      breadcrumb={`${BREADCRUMB} / ${code}`}
      title={title}
      subtitle={`${code} · ${sources.length} source${sources.length === 1 ? "" : "s"}`}
      actions={
        <Button type="button" className="flex items-center gap-2 whitespace-nowrap text-sm" onClick={onUpload}>
          <Upload size={16} aria-hidden />
          Upload source
        </Button>
      }
    >
      {message}
      <PracticeDetailsCard details={details} status={statusText} footer={footer} />
      <PracticeSourcesPanel
        sources={sources}
        statusLabel={(value) => (value === "completed" ? "Indexed" : stageLabel(value))}
        onOpen={onOpenSource}
        onNewVersion={onNewVersion}
      />
    </PageFrame>
  );
}
