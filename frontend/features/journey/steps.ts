/** The six steps a project moves through, and which one the user should be on. */

export const STEPS = [
  { id: "brief", label: "Brief", purpose: "Tell Sheldon what you need, who it is for, and in which format." },
  { id: "sources", label: "Sources", purpose: "Upload the documents the deliverable must be based on." },
  { id: "plan", label: "Plan", purpose: "Check the outline and format, then confirm to start the build." },
  { id: "build", label: "Build", purpose: "Watch the deliverable being generated and checked." },
  { id: "review", label: "Review", purpose: "Read the result and the quality findings, then approve or ask for changes." },
  { id: "deliver", label: "Deliver", purpose: "Download the approved files." },
] as const;

export type StepId = (typeof STEPS)[number]["id"];
export type StepState = "done" | "current" | "attention" | "todo";

export type JourneyFacts = {
  /** Messages the user has sent to Sheldon. */
  userMessages: number;
  /** Uploaded source documents. */
  documents: number;
  /** Sheldon has a plan ready to confirm. */
  planReady: boolean;
  /** Questions Sheldon is still waiting on. */
  openQuestions: number;
  /** A run exists for this project (the plan was confirmed at least once). */
  hasRun: boolean;
  /** Status of the selected run, or "" when there is none. */
  runStatus: string;
};

export type StepInfo = { state: StepState; hint: string };

const BUILDING = new Set(["pending", "plan_ready", "approved", "running", "approval_required"]);

export function stepStates(f: JourneyFacts): Record<StepId, StepInfo> {
  const status = f.hasRun ? f.runStatus : "";
  const building = BUILDING.has(status);
  const blocked = status === "plan_blocked";
  const failed = status === "failed";
  const reviewReady = status === "review_ready";
  const finished = status === "done";

  const brief: StepInfo =
    f.userMessages === 0
      ? { state: "current", hint: "Start by describing the deliverable." }
      : f.openQuestions > 0 && !f.hasRun
        ? { state: "current", hint: `Sheldon has ${f.openQuestions} open question${f.openQuestions === 1 ? "" : "s"}.` }
        : { state: "done", hint: "Brief captured." };

  const sources: StepInfo =
    f.documents > 0
      ? { state: "done", hint: `${f.documents} document${f.documents === 1 ? "" : "s"} uploaded.` }
      : f.userMessages > 0
        ? { state: "attention", hint: "No documents yet. Upload them before confirming the plan so figures can be cited." }
        : { state: "todo", hint: "Upload source documents." };

  const plan: StepInfo = f.hasRun
    ? blocked
      ? { state: "attention", hint: "The plan was blocked by a permission check." }
      : { state: "done", hint: "Plan confirmed." }
    : f.planReady
      ? { state: "current", hint: "The plan is ready. Check the format and confirm." }
      : { state: "todo", hint: f.userMessages > 0 ? "Sheldon is still shaping the plan." : "Comes after the brief." };

  const build: StepInfo = building
    ? { state: "current", hint: "The run is in progress. A deck usually takes 10 to 20 minutes." }
    : failed || reviewReady || finished
      ? { state: "done", hint: "Generation finished." }
      : { state: "todo", hint: "Starts when the plan is confirmed." };

  const review: StepInfo = failed
    ? { state: "attention", hint: "The run failed its checks. See the reason and decide what to change." }
    : reviewReady
      ? { state: "current", hint: "Ready for your review and final approval." }
      : finished
        ? { state: "done", hint: "Approved." }
        : { state: "todo", hint: "Available when the build finishes." };

  const deliver: StepInfo = finished
    ? { state: "current", hint: "Approved files are ready to download." }
    : { state: "todo", hint: "Available after final approval." };

  return { brief, sources, plan, build, review, deliver };
}

/** The step the user most likely needs now. */
export function suggestedStep(f: JourneyFacts): StepId {
  const states = stepStates(f);
  const order: StepId[] = ["review", "build", "plan", "sources", "brief", "deliver"];
  for (const want of ["attention", "current"] as const) {
    // An unfinished brief or missing sources come before later steps; a failed or ready review comes first of all.
    const hit = (want === "attention" ? order : (["brief", "plan", "build", "review", "deliver", "sources"] as StepId[])).find(
      (id) => states[id].state === want,
    );
    if (hit) return hit;
  }
  return "brief";
}

export function isStepId(value: string | null | undefined): value is StepId {
  return STEPS.some((s) => s.id === value);
}
