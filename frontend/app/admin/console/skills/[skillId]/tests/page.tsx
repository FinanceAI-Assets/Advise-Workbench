"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";

import {
  BUTTON_COMPACT,
  BUTTON_SECONDARY,
  Fact,
  Note,
  Panel,
  RecordList,
  RerunTestsButton,
  SKILLS_HOME,
  SkillPageFrame,
  useRouteSkill,
} from "@/components/skill-management";
import { Button } from "@/components/ui/Button";
import { useSkillManagement } from "@/hooks/useSkillManagement";
import { allPassed, passedCount, reviewBlocker, totalCount } from "@/lib/skillManagement";

export default function SkillTestRunPage() {
  const { skill } = useRouteSkill();
  const { submitForReview } = useSkillManagement();
  const router = useRouter();
  const c = skill?.candidate;
  const run = c?.lastTest;

  if (!skill || !c || !run) {
    return (
      <SkillPageFrame skill={skill} crumb="Rerun tests" title={`${skill?.name}: Test rerun`} meta={skill?.code ?? ""}>
        <Panel>
          <p className="text-xs text-[var(--text-muted)]">
            {c ? "The sandbox suite has not run on this candidate yet." : "There is no open candidate to test."}
          </p>
          {c && skill ? <RerunTestsButton skillId={skill.id} label="Run tests" /> : null}
        </Panel>
      </SkillPageFrame>
    );
  }

  const passed = allPassed(run);
  const current = run.revision === c.revision;
  const blocker = reviewBlocker(skill);
  const failing = run.groups.filter((g) => g.passed < g.total);

  return (
    <SkillPageFrame
      skill={skill}
      crumb="Rerun tests"
      title={`${skill.name}: Test rerun`}
      meta={`${run.id} · ${run.revision} · Sandbox fixtures only · ${run.at}`}
    >
      {!current ? (
        <Note tone="warning" title={`These results are for ${run.revision}`}>
          The candidate was saved again as {c.revision}. Rerun the suite before publication review.
        </Note>
      ) : passed ? (
        <Note tone="success" title={`${passedCount(run)} / ${totalCount(run)} tests passed`}>
          {run.regressions.length ? "The corrected stop rule asks for a validated baseline. " : ""}Rerun complete; independent
          release review is still required.
        </Note>
      ) : (
        <Note tone="warning" title={`${passedCount(run)} / ${totalCount(run)} tests passed`}>
          {failing.map((g) => `${g.name}: ${g.outcome}`).join(". ")}. Correct the definition and rerun.
        </Note>
      )}

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-[minmax(0,1fr)_340px]">
        <Panel title="Suite results">
          <RecordList
            label="Suite results"
            columns={["Test group", "Passed", "Outcome"]}
            rows={run.groups.map((g, i) => ({
              key: g.name,
              title: g.name,
              meta: [`${g.passed} / ${g.total}`, g.outcome],
              highlight: i === 0,
            }))}
          />
          {run.regressions.map((r) => (
            <div key={r.fixture} className="space-y-0.5 text-xs">
              <p className="font-semibold text-[var(--text-default)]">
                Regression: {r.name}{" "}
                <span className={r.passed ? "ml-2 text-2xs font-medium text-[var(--accent-green-dark)]" : "ml-2 text-2xs font-medium text-[#A53E37]"}>
                  {r.passed ? "Passed" : "Failed"}
                </span>
              </p>
              <p className="text-2xs text-[var(--text-muted)]">
                Fixture {r.fixture} · Previously failed in {r.previousRun}
              </p>
              {r.passed ? <p className="text-2xs text-[var(--text-default)]">Output: “{r.output}”</p> : null}
            </div>
          ))}
        </Panel>

        <Panel title="Test provenance" className="h-fit">
          <Fact label="Candidate">
            {skill.name} {c.version} · {run.revision}
          </Fact>
          <Fact label="Execution">
            {run.at} · System · {run.durationSec} sec
          </Fact>
          <Fact label="Data">{run.fixtures} synthetic sandbox fixtures · No client data</Fact>
          {c.status === "In review" ? (
            <Link href={`${SKILLS_HOME}/${skill.id}/release`} className="!no-underline">
              <Button type="button" className={BUTTON_COMPACT}>
                Open release review
              </Button>
            </Link>
          ) : blocker ? (
            <div className="flex flex-wrap gap-2">
              <Link href={`${SKILLS_HOME}/new?from=${skill.id}`} className="!no-underline">
                <Button type="button" variant="secondary" className={BUTTON_SECONDARY}>
                  Edit candidate
                </Button>
              </Link>
              <RerunTestsButton skillId={skill.id} />
            </div>
          ) : (
            <Button
              type="button"
              className={BUTTON_COMPACT}
              onClick={() => {
                submitForReview(skill.id);
                router.push(`${SKILLS_HOME}/${skill.id}/release`);
              }}
            >
              Send for publication review
            </Button>
          )}
        </Panel>
      </div>
    </SkillPageFrame>
  );
}
