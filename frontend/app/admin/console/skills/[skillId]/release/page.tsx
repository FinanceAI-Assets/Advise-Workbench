"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import {
  BUTTON_COMPACT,
  Note,
  Panel,
  PublishDialog,
  RecordList,
  type ReleaseResult,
  SKILLS_HOME,
  SkillPageFrame,
  useRouteSkill,
} from "@/components/skill-management";
import { Button } from "@/components/ui/Button";
import { useSkillManagement } from "@/hooks/useSkillManagement";
import { type Skill, stamp } from "@/lib/skillManagement";

export default function SkillReleasePage() {
  const { skill } = useRouteSkill();
  const { publish } = useSkillManagement();
  const router = useRouter();
  // Opens straight away when the candidate arrives from "Send for publication review".
  const [open, setOpen] = useState(skill?.candidate?.status === "In review");
  // The candidate is gone once released, so the dialog keeps what it published (and the skill as reviewed).
  const [released, setReleased] = useState<{ result: ReleaseResult; reviewed: Skill } | null>(null);
  const reviewed = released?.reviewed ?? skill;
  const c = reviewed?.candidate;

  return (
    <SkillPageFrame
      skill={reviewed}
      crumb="Approve & publish"
      title={`${reviewed?.name} release`}
      meta={
        reviewed
          ? `${reviewed.code} · ${c?.version ?? reviewed.published?.version} · Independent approver: ${reviewed.approver} · Latest state: ${released?.result.at ?? reviewed.history[0]?.at ?? ""}`
          : null
      }
    >
      {c ? (
        <Panel title={`${reviewed!.name} · ${reviewed!.code} · ${c.version} candidate`}>
          <p className="text-xs leading-relaxed text-[var(--text-default)]">{c.summary}</p>
          {c.lastTest ? (
            <RecordList
              label="Test comparison"
              columns={["Check", "Previous run", "Candidate"]}
              rows={c.lastTest.groups.map((g, i) => {
                const before = c.previousTest?.groups.find((p) => p.name === g.name);
                return {
                  key: g.name,
                  title: g.name,
                  meta: [before ? `${before.passed} / ${before.total}` : "—", g.passed === g.total ? "Passed" : "Needs correction"],
                  highlight: i === 0,
                };
              })}
            />
          ) : null}
          <Note title="Independent approval">
            {reviewed!.owner} defines the candidate. {reviewed!.approver} approves the release; administrators route the
            candidate but cannot approve it.
          </Note>
          {c.status === "In review" && !released ? (
            <Button type="button" className={BUTTON_COMPACT} onClick={() => setOpen(true)}>
              Approve &amp; publish {c.version}
            </Button>
          ) : !released ? (
            <p className="text-xs text-[var(--text-muted)]">
              Send the candidate for publication review from its{" "}
              <Link href={`${SKILLS_HOME}/${reviewed!.id}/tests`}>test results</Link> first.
            </p>
          ) : null}
        </Panel>
      ) : (
        <Panel>
          <p className="text-xs text-[var(--text-muted)]">No candidate is awaiting release for this skill.</p>
          <Link href={`${SKILLS_HOME}?skill=${reviewed?.id ?? ""}`} className="text-xs">
            View the published registry
          </Link>
        </Panel>
      )}

      {open && reviewed?.candidate ? (
        <PublishDialog
          skill={reviewed}
          result={released?.result ?? null}
          onClose={() => setOpen(false)}
          onViewPublished={() => router.push(`${SKILLS_HOME}?skill=${reviewed.id}`)}
          onPublish={(note) => {
            const candidate = reviewed.candidate!;
            const releaseId = publish(reviewed.id, note);
            if (!releaseId) return;
            setReleased({
              reviewed,
              result: {
                releaseId,
                version: candidate.version,
                approver: reviewed.approver,
                at: stamp(new Date()),
                testId: candidate.lastTest?.id ?? "",
                previousVersion: reviewed.published?.version ?? null,
                pinnedRun: reviewed.pinnedRun,
              },
            });
          }}
        />
      ) : null}
    </SkillPageFrame>
  );
}
