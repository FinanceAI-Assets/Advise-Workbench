"use client";

import { createContext, type ReactNode, useContext, useEffect, useMemo, useState } from "react";

import {
  createSkill,
  type DefinitionDraft,
  publishCandidate,
  runTests,
  sampleState,
  saveCandidate,
  type Skill,
  type SkillState,
  submitForReview,
} from "@/lib/skillManagement";

// Session storage keeps the walkthrough across reloads in this tab; the sample data returns in a new session.
const STORAGE_KEY = "advise_workbench.skillManagement.v1";

function load(): SkillState {
  try {
    const raw = window.sessionStorage.getItem(STORAGE_KEY);
    if (raw) return JSON.parse(raw) as SkillState;
  } catch {
    // Storage can be unavailable (private mode, blocked site data); fall back to the sample data.
  }
  return sampleState();
}

type SkillManagement = {
  ready: boolean;
  skills: Skill[];
  skill: (id: string) => Skill | undefined;
  createSkill: (draft: DefinitionDraft) => string;
  saveCandidate: (skillId: string, draft: DefinitionDraft) => void;
  runTests: (skillId: string) => string;
  submitForReview: (skillId: string) => void;
  publish: (skillId: string, note: string) => string;
  reset: () => void;
};

const SkillManagementContext = createContext<SkillManagement | null>(null);

/** Holds the admin console's skill registry for this browser session. No API is called. */
export function SkillManagementProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<SkillState>(sampleState);
  const [ready, setReady] = useState(false);

  // Read the saved session after mount so the server render and the first client render agree.
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- hydrating from browser storage
    setState(load());
    setReady(true);
  }, []);

  useEffect(() => {
    if (!ready) return;
    try {
      window.sessionStorage.setItem(STORAGE_KEY, JSON.stringify(state));
    } catch {
      // Not persisting is fine: the walkthrough still works for this page view.
    }
  }, [state, ready]);

  // Every action is one user click: it computes the next state from the current one and returns any new id
  // (skill, test run, release) so the caller can navigate straight to it.
  const value = useMemo<SkillManagement>(() => {
    const at = () => new Date();
    return {
      ready,
      skills: state.skills,
      skill: (id) => state.skills.find((s) => s.id === id),
      createSkill: (draft) => {
        const result = createSkill(state, draft, at());
        setState(result.state);
        return result.skillId;
      },
      saveCandidate: (skillId, draft) => setState(saveCandidate(state, skillId, draft, at())),
      runTests: (skillId) => {
        const result = runTests(state, skillId, at());
        setState(result.state);
        return result.testId;
      },
      submitForReview: (skillId) => setState(submitForReview(state, skillId, at())),
      publish: (skillId, note) => {
        const result = publishCandidate(state, skillId, note, at());
        setState(result.state);
        return result.releaseId;
      },
      reset: () => setState(sampleState()),
    };
  }, [state, ready]);

  return <SkillManagementContext.Provider value={value}>{children}</SkillManagementContext.Provider>;
}

export function useSkillManagement(): SkillManagement {
  const context = useContext(SkillManagementContext);
  if (!context) throw new Error("useSkillManagement must be used inside SkillManagementProvider");
  return context;
}
