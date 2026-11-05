import { describe, expect, it } from "vitest";

import { isStepId, stepStates, suggestedStep, type JourneyFacts } from "./steps";

const base: JourneyFacts = { userMessages: 0, documents: 0, planReady: false, openQuestions: 0, hasRun: false, runStatus: "" };

describe("journey steps", () => {
  it("starts at the brief", () => {
    expect(suggestedStep(base)).toBe("brief");
    expect(stepStates(base).brief.state).toBe("current");
    expect(stepStates(base).sources.state).toBe("todo");
  });

  it("flags missing sources once the brief has started", () => {
    const facts = { ...base, userMessages: 2 };
    expect(stepStates(facts).sources.state).toBe("attention");
    expect(suggestedStep(facts)).toBe("sources");
  });

  it("stays on the brief while Sheldon has open questions", () => {
    const facts = { ...base, userMessages: 1, documents: 3, openQuestions: 2 };
    expect(stepStates(facts).brief).toEqual({ state: "current", hint: "Sheldon has 2 open questions." });
    expect(suggestedStep(facts)).toBe("brief");
  });

  it("moves to the plan when it is ready to confirm", () => {
    const facts = { ...base, userMessages: 3, documents: 3, planReady: true };
    expect(stepStates(facts).plan.state).toBe("current");
    expect(suggestedStep(facts)).toBe("plan");
  });

  it("shows the build while a run is in progress", () => {
    const facts = { ...base, userMessages: 3, documents: 3, hasRun: true, runStatus: "running" };
    const states = stepStates(facts);
    expect(states.plan.state).toBe("done");
    expect(states.build.state).toBe("current");
    expect(states.review.state).toBe("todo");
    expect(suggestedStep(facts)).toBe("build");
  });

  it("sends a failed run to review with attention", () => {
    const facts = { ...base, userMessages: 3, documents: 3, hasRun: true, runStatus: "failed" };
    expect(stepStates(facts).review.state).toBe("attention");
    expect(stepStates(facts).build.state).toBe("done");
    expect(suggestedStep(facts)).toBe("review");
  });

  it("asks for review when the run is ready, and delivers once approved", () => {
    const ready = { ...base, userMessages: 3, documents: 3, hasRun: true, runStatus: "review_ready" };
    expect(suggestedStep(ready)).toBe("review");
    const done = { ...ready, runStatus: "done" };
    expect(stepStates(done).review.state).toBe("done");
    expect(suggestedStep(done)).toBe("deliver");
  });

  it("marks a blocked plan", () => {
    const facts = { ...base, userMessages: 3, documents: 1, hasRun: true, runStatus: "plan_blocked" };
    expect(stepStates(facts).plan.state).toBe("attention");
    expect(suggestedStep(facts)).toBe("plan");
  });

  it("recognises step ids", () => {
    expect(isStepId("plan")).toBe(true);
    expect(isStepId("nope")).toBe(false);
    expect(isStepId(null)).toBe(false);
  });
});
