"use client";

import Link from "next/link";
import { useState } from "react";

import {
  AdminStatCard,
  ControlsAuditPanel,
  IngestionHealthPanel,
  PendingApprovalsTable,
  RiskQueueTable,
} from "@/components/admin-console";
import { Button } from "@/components/ui/Button";
import { ExportButton, RecordsTable } from "@/components/workbench/AdminControls";
import { ErrorNote, PageFrame, PageSkeleton } from "@/components/workbench/PageFrame";
import { useAdminOverviewQuery } from "@/hooks/useAdminConsole";

export default function AdminConsoleOverviewPage() {
  const overview = useAdminOverviewQuery();
  const [showJobs, setShowJobs] = useState(false);

  if (overview.isPending) return <PageSkeleton />;
  const data = overview.data;
  if (!data) return <ErrorNote error={overview.error} />;

  return (
    <PageFrame
      breadcrumb="Admin console / Operations"
      title="Platform overview"
      subtitle="Operational oversight across the advisory workspace. Administrative rights do not grant access to engagement content."
      actions={<ExportButton report="reviews" label="Export report" />}
    >
      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        {data.stats.map((stat) => (
          <AdminStatCard key={stat.id} {...stat} />
        ))}
      </section>

      <div className="grid gap-4 lg:grid-cols-[1fr_380px]">
        <PendingApprovalsTable rows={data.pendingApprovals} total={data.pendingApprovalsTotal} />
        <IngestionHealthPanel
          items={data.ingestionHealth}
          updatedMeta={data.ingestionUpdatedMeta}
          warning={data.ingestionWarning}
          actions={
            <Button variant="secondary" type="button" className="w-full text-sm" onClick={() => setShowJobs((prev) => !prev)}>
              {showJobs ? "Hide ingestion jobs" : "View ingestion jobs"}
            </Button>
          }
        />
      </div>

      {showJobs ? (
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
      ) : null}

      <div className="grid gap-4 lg:grid-cols-[1fr_380px]">
        <RiskQueueTable rows={data.riskQueue} openCount={data.riskQueueOpenCount} footnote={data.riskQueueFootnote} />
        <ControlsAuditPanel
          items={data.controlsAudit}
          auditEvent={data.controlsAuditEvent}
          actions={
            <Link href="/admin/console/reviews?tab=audit" className="block !no-underline">
              <Button variant="secondary" type="button" className="w-full text-sm">
                Open governance
              </Button>
            </Link>
          }
        />
      </div>
    </PageFrame>
  );
}
