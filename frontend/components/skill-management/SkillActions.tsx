"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { type ReactNode, useEffect, useRef, useState } from "react";

import { BUTTON_COMPACT, Panel, SKILLS_HOME, SkillTabs, type SkillTabKey } from "@/components/skill-management/SkillParts";
import { Button } from "@/components/ui/Button";
import { BackButton } from "@/components/workbench/BackButton";
import { PageFrame } from "@/components/workbench/PageFrame";
import { useSkillManagement } from "@/hooks/useSkillManagement";
import type { Skill } from "@/lib/skillManagement";

// The sandbox suite runs in the browser; a short pause shows the run starting before the results open.
const SIMULATED_RUN_MS = 1200;

/** Run the sandbox suite on the candidate's saved revision, then open the results. */
export function RerunTestsButton({ skillId, label = "Rerun tests", className }: { skillId: string; label?: string; className?: string }) {
  const { runTests } = useSkillManagement();
  const router = useRouter();
  const [running, setRunning] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => () => {
    if (timer.current) clearTimeout(timer.current);
  }, []);

  return (
    <Button
      type="button"
      disabled={running}
      aria-live="polite"
      className={className ?? BUTTON_COMPACT}
      onClick={() => {
        setRunning(true);
        timer.current = setTimeout(() => {
          runTests(skillId);
          router.push(`${SKILLS_HOME}/${skillId}/tests`);
        }, SIMULATED_RUN_MS);
      }}
    >
      {running ? "Running sandbox suite…" : label}
    </Button>
  );
}

/** The skill named by the route's [skillId], or undefined while unknown. */
export function useRouteSkill(): { skillId: string; skill: Skill | undefined } {
  const params = useParams<{ skillId: string }>();
  const { skill } = useSkillManagement();
  const skillId = decodeURIComponent(params.skillId ?? "");
  return { skillId, skill: skill(skillId) };
}

/** Breadcrumb, title, meta line and tabs for one skill's pages; handles an unknown skill id. */
export function SkillPageFrame({
  skill,
  crumb,
  title,
  meta,
  tab,
  actions,
  children,
}: {
  skill: Skill | undefined;
  crumb: string;
  title: string;
  meta: ReactNode;
  tab?: SkillTabKey;
  actions?: ReactNode;
  children: ReactNode;
}) {
  if (!skill) {
    return (
      <PageFrame
        back={<BackButton href={SKILLS_HOME} label="Back to the skill registry" />}
        breadcrumb="Admin console / Skills management"
        title="Skill not found"
      >
        <Panel>
          <p className="text-xs text-[var(--text-muted)]">This skill is not in the registry for this session.</p>
          <Link href={SKILLS_HOME} className="text-xs">
            Back to the skill registry
          </Link>
        </Panel>
      </PageFrame>
    );
  }
  return (
    <PageFrame
      // Definition is the skill's first screen, so it returns to the registry; every other screen returns to Definition.
      back={tab === "definition" ? <BackButton href={SKILLS_HOME} label="Back to the skill registry" /> : <BackButton href={`${SKILLS_HOME}/${skill.id}`} label="Back to skill" />}
      breadcrumb={`Admin console / Skills management / ${crumb}`}
      title={title}
      subtitle={meta}
      actions={actions}
    >
      <SkillTabs skillId={skill.id} active={tab} />
      {children}
    </PageFrame>
  );
}

/** "SK-008 · v2.2 candidate" or "SK-003 · v1.6 published": the version the tabs describe. */
export function versionLabel(skill: Skill): string {
  if (skill.candidate) return `${skill.code} · ${skill.candidate.version} candidate`;
  return `${skill.code} · ${skill.published?.version ?? ""} published`;
}
