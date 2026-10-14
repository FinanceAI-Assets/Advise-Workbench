"use client";

import { useState } from "react";

import { IngestionJobPanel, PracticeInventoryTable, QualityReviewPanel } from "@/components/admin-console";
import { EngagementStepper } from "@/components/engagements";
import { Card } from "@/components/ui/Card";
import { Input } from "@/components/ui/Input";
import { Select } from "@/components/ui/Select";
import { ReasonAction, RecordsTable } from "@/components/workbench/AdminControls";
import { ErrorNote, PageFrame, PageSkeleton } from "@/components/workbench/PageFrame";
import { useAdminLibraryQuery } from "@/hooks/useAdminConsole";

export default function AdminConsoleLibraryPage() {
  const library = useAdminLibraryQuery();
  const [query, setQuery] = useState("");
  const [lifecycle, setLifecycle] = useState("all");
  const [activeId, setActiveId] = useState<string | null>(null);

  if (library.isPending) return <PageSkeleton />;
  const data = library.data;
  if (!data) {
    return (
      <PageFrame breadcrumb="Admin console / Leading Practice Library" title="Library management">
        <ErrorNote error={library.error} />
      </PageFrame>
    );
  }

  const needle = query.trim().toLowerCase();
  const rows = data.practiceInventory.filter(
    (row) =>
      (lifecycle === "all" || (lifecycle === "published" ? row.lifecycle === "Approved" : row.lifecycle !== "Approved")) &&
      (!needle || `${row.practiceSource} ${row.version}`.toLowerCase().includes(needle))
  );
  const reviewed = data.qualityReview;
  const selectedId = activeId ?? reviewed.id;
  const selectedRow = data.practiceInventory.find((row) => row.id === selectedId);

  return (
    <PageFrame
      breadcrumb="Admin console / Leading Practice Library"
      title="Library management"
      subtitle="Ingest, verify and publish versioned practices. Only approved releases are available for user retrieval."
    >
      <EngagementStepper steps={data.pipelineSteps} />

      <div className="grid gap-4 lg:grid-cols-[1fr_380px]">
        <div className="space-y-4">
          <div className="flex flex-wrap items-center gap-3">
            <Input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search practice title or version"
              className="min-w-[260px] flex-1"
            />
            <Select aria-label="Lifecycle" value={lifecycle} onChange={(e) => setLifecycle(e.target.value)} className="w-auto">
              <option value="all">Lifecycle: All</option>
              <option value="published">Lifecycle: Published</option>
              <option value="review">Lifecycle: In review</option>
            </Select>
            <span className="ml-auto text-xs text-[var(--text-muted)]">
              {rows.length} of {data.practiceInventoryTotal}
            </span>
          </div>
          <PracticeInventoryTable rows={rows} activeId={selectedId} onSelect={setActiveId} />
          <IngestionJobPanel job={data.latestIngestionJob} />
        </div>

        {selectedId === reviewed.id ? (
          <QualityReviewPanel
            review={reviewed}
            actions={
              <div className="flex flex-wrap items-start gap-2">
                <ReasonAction
                  label="Request correction"
                  build={(reason) => ({ path: `/library/${reviewed.id}/request-correction`, body: { reason } })}
                />
                <ReasonAction
                  primary
                  label="Approve & publish"
                  build={(reason) => ({ path: `/library/${reviewed.id}/publish`, body: { reason } })}
                />
              </div>
            }
          />
        ) : (
          <Card className="h-fit space-y-3">
            <h2 className="text-base font-semibold text-[var(--text-default)]">{selectedRow?.practiceSource}</h2>
            <p className="text-sm text-[var(--text-muted)]">
              {selectedRow?.version} · {selectedRow?.indexing} · {selectedRow?.lifecycle}
            </p>
            <p className="text-sm text-[var(--text-default)]">
              No quality review is open for this practice. Publication follows its independent review.
            </p>
            {selectedRow && selectedRow.lifecycle !== "Approved" ? (
              <ReasonAction
                primary
                label="Approve & publish"
                build={(reason) => ({ path: `/library/${selectedRow.id}/publish`, body: { reason } })}
              />
            ) : null}
          </Card>
        )}
      </div>

      <RecordsTable
        title="Ingestion jobs"
        columns={[
          ["id", "Job"],
          ["source", "Source"],
          ["stage", "Stage"],
          ["submittedBy", "Submitted by"],
          ["outcome", "Outcome"],
          ["detail", "Detail"],
        ]}
        rows={data.ingestionJobs}
        empty="No ingestion jobs recorded."
      />
    </PageFrame>
  );
}
