import { describe, expect, it } from "vitest";

import {
  candidateGate,
  createSkill,
  draftFrom,
  emptyDraft,
  nextVersion,
  parseInputs,
  publishCandidate,
  releaseGates,
  reviewBlocker,
  runTests,
  sampleState,
  saveCandidate,
  submitForReview,
  validateDraft,
} from "./skillManagement";

const NOW = new Date(2026, 9, 8, 10, 25);
const skill = (state: ReturnType<typeof sampleState>, id: string) => state.skills.find((s) => s.id === id)!;

describe("skill management", () => {
  it("bumps versions and parses input schemas", () => {
    expect(nextVersion("v2.1")).toBe("v2.2");
    expect(nextVersion(undefined)).toBe("v0.1");
    expect(parseInputs("brief:string · sources:Source[] · baseline?:Measure[]")).toEqual([
      { name: "brief", type: "string", rule: "Required", required: true },
      { name: "sources", type: "Source[]", rule: "Required", required: true },
      { name: "baseline", type: "Measure[]", rule: "Optional", required: false },
    ]);
  });

  it("requires a stop rule, a human review step and an independent approver", () => {
    const draft = { ...emptyDraft(), name: "Pilot adoption assessor", inputSchema: "brief:string", outputSchema: "DOCX / 4 pages" };
    expect(validateDraft({ ...draft, contract: "ROLE: Analyst." }).problems).toEqual([
      "Add a missing-evidence rule starting with “STOP:”.",
      "State the human review or approval step.",
    ]);
    const complete = { ...draft, contract: "ROLE: Analyst. STOP: Ask for missing baselines. REVIEW: Human approval before export." };
    expect(validateDraft(complete).ok).toBe(true);
    expect(validateDraft({ ...complete, approver: complete.owner }).problems).toEqual([
      "The independent approver must differ from the owner.",
    ]);
  });

  it("saves a new skill as an unpublished v0.1 candidate", () => {
    const draft = {
      ...emptyDraft(),
      name: "Pilot adoption assessor",
      contract: "ROLE: Analyst. STOP: Ask for missing baselines. REVIEW: Human approval before export.",
      inputSchema: "brief:string · baseline:Measure[]",
      outputSchema: "DOCX / 4 pages · Evidence register",
    };
    const { state, skillId } = createSkill(sampleState(), draft, NOW);
    const created = skill(state, skillId);
    expect(created.code).toBe("SK-012");
    expect(created.published).toBeNull();
    expect(created.candidate).toMatchObject({ version: "v0.1", revision: "C-012-01a", status: "Saved", savedAt: "08 Oct, 10:25" });
    expect(created.candidate!.contract).toEqual(["ROLE: Analyst.", "STOP: Ask for missing baselines. REVIEW: Human approval before export."]);
    expect(candidateGate(created)).toBe("Saved · Rerun required");
  });

  it("walks the roadmap builder candidate from rerun to release", () => {
    let state = sampleState();
    expect(reviewBlocker(skill(state, "sk-008"))).toBe("Rerun the sandbox suite on the saved revision first.");

    const rerun = runTests(state, "sk-008", NOW);
    state = rerun.state;
    const test = skill(state, "sk-008").candidate!.lastTest!;
    expect(rerun.testId).toBe("TEST-063");
    expect(test.groups.map((g) => `${g.passed}/${g.total}`)).toEqual(["6/6", "4/4", "4/4", "4/4"]);
    expect(test.regressions).toEqual([
      expect.objectContaining({ name: "Missing benefits baseline", fixture: "F-018", previousRun: "TEST-062", passed: true }),
    ]);
    expect(reviewBlocker(skill(state, "sk-008"))).toBeNull();

    state = submitForReview(state, "sk-008", NOW);
    expect(releaseGates(skill(state, "sk-008")).every((g) => g.ok)).toBe(true);
    expect(publishCandidate(state, "sk-008", "too short", NOW).releaseId).toBe("");

    const release = publishCandidate(state, "sk-008", "Verified missing-baseline regression and permission tests.", NOW);
    const released = skill(release.state, "sk-008");
    expect(release.releaseId).toBe("PUB-008-22");
    expect(released.candidate).toBeNull();
    expect(released.published).toMatchObject({ version: "v2.2", approvedBy: "Priya Shah", publishedOn: "08 Oct 2026" });
    expect(released.history.slice(0, 2).map((h) => h.title)).toEqual(["v2.2 published", "v2.1 superseded"]);
  });

  it("fails the insufficient-evidence fixture when the contract has no stop rule", () => {
    const state = sampleState();
    const draft = { ...draftFrom(skill(state, "sk-003")), contract: "ROLE: Summarize interviews. REVIEW: Human approval." };
    const saved = saveCandidate(state, "sk-003", draft, NOW);
    expect(skill(saved, "sk-003").candidate).toMatchObject({ version: "v1.7", revision: "C-003-17a" });
    const tested = runTests(saved, "sk-003", NOW).state;
    const candidate = skill(tested, "sk-003").candidate!;
    expect(candidate.lastTest!.groups[3]).toMatchObject({ passed: 3, total: 4 });
    expect(reviewBlocker(skill(tested, "sk-003"))).toBe("All sandbox tests must pass before publication review.");
  });
});
