"use client";

import { Check, Download, Send } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";

import { EngagementStepper } from "@/components/engagements";
import { ApprovalPanel, DraftPreviewPanel, EvidenceChecksTable, ReviewCommentsPanel } from "@/components/reviews";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { Textarea } from "@/components/ui/Textarea";
import { ErrorNote, PageFrame, PageSkeleton } from "@/components/workbench/PageFrame";
import { useReviewActions, useReviewQuery } from "@/hooks/useWorkbench";
import { useAuth } from "@/lib/auth-context";
import { downloadFile } from "@/lib/workbenchApi";

// One review: the owner addresses comments and resubmits; the assigned reviewer
// comments, requests changes or approves. The server decides who may do what.
export default function ReviewDetailPage() {
  const params = useParams();
  const raw = typeof params.id === "string" ? params.id : Array.isArray(params.id) ? (params.id[0] ?? "") : "";
  const id = decodeURIComponent(raw);
  const review = useReviewQuery(id);
  const actions = useReviewActions(id);
  const [note, setNote] = useState("");
  const { api } = useAuth();
  const [downloadError, setDownloadError] = useState<unknown>(null);

  if (review.isPending) return <PageSkeleton />;
  if (review.isError || !review.data) {
    return (
      <main className="space-y-4">
        <EmptyState title="Review not found" description="It may have been removed, or you don't have access to it.">
          <Link href="/reviews">
            <Button variant="secondary">Back to reviews</Button>
          </Link>
        </EmptyState>
      </main>
    );
  }

  const data = review.data;
  const busy =
    actions.resolve.isPending || actions.submitRevision.isPending || actions.decide.isPending || actions.comment.isPending;
  const error =
    actions.resolve.error ?? actions.submitRevision.error ?? actions.decide.error ?? actions.comment.error ?? downloadError;
  // An approved deck or document can be downloaded right here.
  const downloadable =
    data.state === "Approved" && data.projectId && data.runId && (data.artifactType === "pptx" || data.artifactType === "docx");
  async function download() {
    setDownloadError(null);
    try {
      await downloadFile(
        api,
        `/api/runs/${data.projectId}/${data.runId}/artifacts/${data.artifactType}/download`,
        `${data.artifactName}.${data.artifactType}`
      );
    } catch (err) {
      setDownloadError(err);
    }
  }

  return (
    <PageFrame
      breadcrumb={
        <>
          {data.engagementName} / <Link href="/reviews">Reviews</Link> / {data.code}
        </>
      }
      title={`Review: ${data.artifactName}`}
      subtitle={`${data.code} · ${data.versionLabel} · Owner: ${data.owner} · Reviewer: ${data.reviewer} · Due ${data.dueDate} · ${data.state}`}
      actions={
        <>
          {downloadable ? (
            <Button className="flex items-center gap-2" onClick={() => void download()}>
              <Download size={16} aria-hidden />
              Download {data.artifactType.toUpperCase()}
            </Button>
          ) : null}
          {data.projectId ? (
            <Link href={`/engagements/${data.projectId}/deliverables`} className="!no-underline">
              <Button variant="secondary">Open full artifact</Button>
            </Link>
          ) : null}
          {data.canRevise ? (
            <Button
              className="flex items-center gap-2"
              disabled={busy || data.openCount > 0}
              title={data.openCount > 0 ? "Address every open comment first" : undefined}
              onClick={() => actions.submitRevision.mutate(note)}
            >
              <Send size={16} aria-hidden />
              Submit revised draft
            </Button>
          ) : null}
          {data.canDecide ? (
            <Button
              className="flex items-center gap-2"
              disabled={busy || data.openCount > 0}
              title={data.openCount > 0 ? "Resolve the open comments first" : undefined}
              onClick={() => actions.decide.mutate({ decision: "approve", note })}
            >
              <Check size={16} aria-hidden />
              Approve this version
            </Button>
          ) : null}
        </>
      }
    >
      <EngagementStepper steps={data.steps} />
      <ErrorNote error={error} />

      <div className="grid gap-4 lg:grid-cols-[1fr_380px]">
        <div className="space-y-4">
          {data.slide ? (
            <DraftPreviewPanel
              slide={data.slide}
              versionLabel={data.versionLabel}
              commentCount={data.slideCommentCount}
              state={data.state}
              artifactHref={data.projectId ? `/engagements/${data.projectId}/deliverables` : undefined}
            />
          ) : (
            <Card>
              <p className="text-sm text-[var(--text-muted)]">
                No preview is stored for this item. Open the full artifact to read it.
              </p>
            </Card>
          )}
          {data.evidenceChecks.length > 0 ? (
            <EvidenceChecksTable checks={data.evidenceChecks} runMeta={data.evidenceChecksRunMeta} />
          ) : null}
        </div>

        <div className="space-y-4">
          <ReviewCommentsPanel
            comments={data.comments}
            openCount={data.openCount}
            resolvedCount={data.resolvedCount}
            onResolve={data.canComment ? (commentId) => actions.resolve.mutate(commentId) : undefined}
          />

          {data.canComment && data.state !== "Approved" ? (
            <Card className="space-y-3">
              <h2 className="text-base font-semibold text-[var(--text-default)]">
                {data.canDecide ? "Comment or request changes" : "Reply to the reviewer"}
              </h2>
              <Textarea
                rows={3}
                value={note}
                onChange={(e) => setNote(e.target.value)}
                placeholder={data.canDecide ? "Say what needs to change…" : "Describe what you changed…"}
              />
              <div className="flex flex-wrap gap-2">
                <Button
                  variant="secondary"
                  disabled={busy || note.trim().length < 3}
                  onClick={() =>
                    actions.comment.mutate({ title: "", body: note.trim() }, { onSuccess: () => setNote("") })
                  }
                >
                  Add comment
                </Button>
                {data.canDecide ? (
                  <Button
                    variant="secondary"
                    disabled={busy || note.trim().length < 3}
                    onClick={() =>
                      actions.decide.mutate(
                        { decision: "request_changes", note: note.trim() },
                        { onSuccess: () => setNote("") }
                      )
                    }
                  >
                    Request changes
                  </Button>
                ) : null}
              </div>
            </Card>
          ) : null}

          <ApprovalPanel
            approverName={data.approverName}
            approverRole={data.approverRole}
            status={data.approvalStatus}
            timeline={data.approvalTimeline}
          />
        </div>
      </div>
    </PageFrame>
  );
}
