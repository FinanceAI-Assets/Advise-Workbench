/**
 * Skill management for the admin console, held entirely in the browser.
 *
 * A skill has at most one published version (immutable, used by engagement runs) and at most one candidate
 * (editable, sandbox-tested, released only after independent approval). The functions below are pure: each
 * takes the current state and returns the next one, so the screens stay simple and the flow is unit-tested.
 * No API is called; `useSkillManagement` keeps this state for the browser session.
 */

export type SchemaField = { name: string; type: string; rule: string; required: boolean };
export type OutputContract = { name: string; contract: string; validation: string };

export type SkillDefinition = {
  version: string;
  /** One paragraph per entry; a paragraph starting with "STOP:" is the missing-evidence rule. */
  contract: string[];
  summary: string;
  inputSummary: string;
  outputSummary: string;
  formats: string;
  inputs: SchemaField[];
  outputs: OutputContract[];
  missingEvidence: string;
  fixture: string;
  permittedRoles: string;
};

export type TestGroup = { name: string; passed: number; total: number; outcome: string };
export type TestRun = {
  id: string;
  revision: string;
  at: string;
  durationSec: number;
  fixtures: number;
  groups: TestGroup[];
  /** Fixtures that failed in the previous run and are re-checked by this one. */
  regressions: Array<{ name: string; fixture: string; previousRun: string; output: string; passed: boolean }>;
};

export type CandidateStatus = "Draft definition" | "Saved" | "In testing" | "Tests passed" | "In review";

export type Candidate = SkillDefinition & {
  revision: string;
  status: CandidateStatus;
  savedAt: string;
  change: string;
  changes: Array<{ title: string; detail: string }>;
  lastTest: TestRun | null;
  previousTest: TestRun | null;
};

export type Published = SkillDefinition & { approvedBy: string; publishedOn: string; releaseId: string };

export type HistoryEvent = { title: string; actor: string; at: string; lifecycle: string };

export type Skill = {
  id: string;
  code: string;
  name: string;
  category: string;
  owner: string;
  approver: string;
  published: Published | null;
  candidate: Candidate | null;
  history: HistoryEvent[];
  /** A run that pins the published version, shown to explain that releases never change earlier runs. */
  pinnedRun: string;
};

export type SkillState = { skills: Skill[]; nextTest: number; nextSkill: number };

export type DefinitionDraft = {
  name: string;
  category: string;
  contract: string;
  inputSchema: string;
  outputSchema: string;
  permittedRoles: string;
  owner: string;
  approver: string;
};

export const PEOPLE = ["Maya Patel", "Priya Shah", "Sam Rivera", "Alex Chen"];
export const CATEGORIES = ["Transformation", "Operating model", "Discovery", "Governance", "Evidence", "Storytelling"];
const STOP_RULE = /^STOP:/i;
const HUMAN_REVIEW = /\b(REVIEW|human approval|human review)\b/i;
const MISSING_EVIDENCE_OUTPUT = "Please provide a validated benefits baseline. Until then, benefits remain directional.";

// --- formatting ----------------------------------------------------------------------------------------------------

const two = (n: number) => String(n).padStart(2, "0");
const month = (d: Date) => d.toLocaleString("en-GB", { month: "short" });
/** "08 Oct, 10:20" for page meta lines. */
export const stamp = (d: Date) => `${two(d.getDate())} ${month(d)}, ${two(d.getHours())}:${two(d.getMinutes())}`;
/** "08 Oct 10:20" for history rows. */
const historyStamp = (d: Date) => `${two(d.getDate())} ${month(d)} ${two(d.getHours())}:${two(d.getMinutes())}`;
const day = (d: Date) => `${two(d.getDate())} ${month(d)} ${d.getFullYear()}`;

/** v2.1 → v2.2; a new skill starts at v0.1. */
export function nextVersion(version: string | undefined): string {
  const match = /^v(\d+)\.(\d+)$/.exec(version ?? "");
  return match ? `v${match[1]}.${Number(match[2]) + 1}` : "v0.1";
}

/** C-008-22a, C-008-22b, …: skill number, version digits, then a letter per saved revision. */
function nextRevision(skill: Pick<Skill, "code">, version: string, previous?: string): string {
  const base = `C-${skill.code.replace(/^SK-/, "")}-${version.replace(/\D/g, "")}`;
  if (previous?.startsWith(base)) return `${base}${String.fromCharCode(previous.charCodeAt(previous.length - 1) + 1)}`;
  return `${base}a`;
}

export const passedCount = (run: TestRun) => run.groups.reduce((sum, g) => sum + g.passed, 0);
export const totalCount = (run: TestRun) => run.groups.reduce((sum, g) => sum + g.total, 0);
export const allPassed = (run: TestRun | null) => Boolean(run) && passedCount(run as TestRun) === totalCount(run as TestRun);
export const hasStopRule = (contract: string[]) => contract.some((p) => STOP_RULE.test(p.trim()));

// --- definition drafts ---------------------------------------------------------------------------------------------

export function emptyDraft(): DefinitionDraft {
  return {
    name: "",
    category: CATEGORIES[0],
    contract: "",
    inputSchema: "",
    outputSchema: "",
    permittedRoles: "",
    owner: PEOPLE[0],
    approver: PEOPLE[1],
  };
}

/** A draft for the next candidate of a published skill, starting from its published definition. */
export function draftFrom(skill: Skill): DefinitionDraft {
  const source = skill.candidate ?? skill.published;
  return {
    name: skill.name,
    category: skill.category,
    contract: source?.contract.join("\n") ?? "",
    inputSchema: source?.inputs.map((f) => `${f.name}${f.required ? "" : "?"}:${f.type}`).join(" · ") ?? "",
    outputSchema: source?.outputs.map((o) => o.name).join(" · ") ?? "",
    permittedRoles: source?.permittedRoles ?? "",
    owner: skill.owner,
    approver: skill.approver,
  };
}

export type DraftCheck = { ok: boolean; problems: string[] };

/** What stops a draft from being saved as a candidate. */
export function validateDraft(draft: DefinitionDraft): DraftCheck {
  const problems: string[] = [];
  if (draft.name.trim().length < 3) problems.push("Skill name is required.");
  if (!draft.contract.trim()) problems.push("Instruction contract is required.");
  else {
    if (!hasStopRule(contractParagraphs(draft.contract))) problems.push("Add a missing-evidence rule starting with “STOP:”.");
    if (!HUMAN_REVIEW.test(draft.contract)) problems.push("State the human review or approval step.");
  }
  if (!parseInputs(draft.inputSchema).length) problems.push("Input schema needs at least one name:type field.");
  if (!parseOutputs(draft.outputSchema).length) problems.push("Output schema is required.");
  if (draft.owner === draft.approver) problems.push("The independent approver must differ from the owner.");
  return { ok: problems.length === 0, problems };
}

/** "brief:string · sources:Source[] · baseline?:Measure[]" → fields; "?" marks an optional field. */
export function parseInputs(schema: string): SchemaField[] {
  return schema
    .split(/[·,\n]/)
    .map((part) => part.trim())
    .filter((part) => part.includes(":"))
    .map((part) => {
      const [rawName, ...rest] = part.split(":");
      const optional = rawName.trim().endsWith("?");
      const name = rawName.trim().replace(/\?$/, "");
      return { name, type: rest.join(":").trim(), rule: optional ? "Optional" : "Required", required: !optional };
    })
    .filter((field) => field.name && field.type);
}

export function parseOutputs(schema: string): OutputContract[] {
  return schema
    .split(/[·\n]/)
    .map((part) => part.trim())
    .filter(Boolean)
    .map((name) => ({ name, contract: "Defined in the candidate contract", validation: "Schema check in sandbox" }));
}

function contractParagraphs(contract: string): string[] {
  // Keep authored paragraphs; a single-line contract is split so its STOP rule stands on its own.
  return contract
    .split(/\n+|\s(?=STOP:)/)
    .map((p) => p.trim())
    .filter(Boolean);
}

function definitionFromDraft(draft: DefinitionDraft, version: string, base?: SkillDefinition): SkillDefinition {
  const inputs = parseInputs(draft.inputSchema);
  const outputs = parseOutputs(draft.outputSchema);
  // Keep the richer published rule text for fields and outputs whose names did not change.
  const known = new Map(base?.inputs.map((f) => [f.name, f]));
  const knownOut = new Map(base?.outputs.map((o) => [o.name, o]));
  return {
    version,
    contract: contractParagraphs(draft.contract),
    summary: contractParagraphs(draft.contract)[0] ?? "",
    inputSummary: inputs.map((f) => f.name).join(" · "),
    outputSummary: outputs.map((o) => o.name).join(" · "),
    formats: outputs.map((o) => o.name.split(/\s|\//)[0]).filter((f) => /^[A-Z]{3,4}$/.test(f)).join(" + ") || "Document",
    inputs: inputs.map((f) => ({ ...f, rule: known.get(f.name)?.rule ?? f.rule })),
    outputs: outputs.map((o) => knownOut.get(o.name) ?? o),
    missingEvidence: base?.missingEvidence ?? "If required evidence is absent, ask for it or label the result as an assumption.",
    fixture: base?.fixture ?? inputs.map((f) => `${f.name}: …`).join(" · "),
    permittedRoles: draft.permittedRoles.trim() || "Engagement lead, Contributor · Scoped engagement only",
  };
}

/** The definition part of a candidate, without its review state. */
function definitionOf(c: Candidate): SkillDefinition {
  return {
    version: c.version,
    contract: c.contract,
    summary: c.summary,
    inputSummary: c.inputSummary,
    outputSummary: c.outputSummary,
    formats: c.formats,
    inputs: c.inputs,
    outputs: c.outputs,
    missingEvidence: c.missingEvidence,
    fixture: c.fixture,
    permittedRoles: c.permittedRoles,
  };
}

/** The candidate registry's gate column: where the candidate stands and what it needs next. */
export function candidateGate(skill: Skill): string {
  const c = skill.candidate;
  if (!c) return "";
  if (c.status === "In review") return "In review · Awaiting approval";
  if (c.status === "Saved" && (!c.lastTest || c.lastTest.revision !== c.revision)) return "Saved · Rerun required";
  if (c.status === "Saved") return "Saved · Tests failing";
  if (c.status === "Tests passed") return "Tests passed · Ready for review";
  return c.status;
}

// --- transitions ---------------------------------------------------------------------------------------------------

const replace = (state: SkillState, skill: Skill): SkillState => ({
  ...state,
  skills: state.skills.map((s) => (s.id === skill.id ? skill : s)),
});

/** Save a brand-new skill as its first candidate (v0.1). Nothing is published. */
export function createSkill(state: SkillState, draft: DefinitionDraft, now: Date): { state: SkillState; skillId: string } {
  const number = state.nextSkill;
  const code = `SK-${String(number).padStart(3, "0")}`;
  const id = code.toLowerCase();
  const version = nextVersion(undefined);
  const skill: Skill = {
    id,
    code,
    name: draft.name.trim(),
    category: draft.category,
    owner: draft.owner,
    approver: draft.approver,
    published: null,
    candidate: null,
    history: [],
    pinnedRun: "",
  };
  skill.candidate = {
    ...definitionFromDraft(draft, version),
    revision: nextRevision(skill, version),
    status: "Saved",
    savedAt: stamp(now),
    change: "New skill definition",
    changes: [{ title: "New skill", detail: "First candidate definition" }],
    lastTest: null,
    previousTest: null,
  };
  skill.history = [
    { title: `${version} · ${skill.candidate.revision} saved`, actor: draft.owner, at: historyStamp(now), lifecycle: "Candidate · New skill" },
  ];
  return { state: { ...state, skills: [skill, ...state.skills], nextSkill: number + 1 }, skillId: id };
}

/** Save the next candidate of an existing skill (or a new revision of its open candidate). */
export function saveCandidate(state: SkillState, skillId: string, draft: DefinitionDraft, now: Date): SkillState {
  const skill = state.skills.find((s) => s.id === skillId);
  if (!skill) return state;
  const version = skill.candidate?.version ?? nextVersion(skill.published?.version);
  const revision = nextRevision(skill, version, skill.candidate?.revision);
  const definition = definitionFromDraft(draft, version, skill.candidate ?? skill.published ?? undefined);
  const changes = describeChanges(skill.published, definition);
  const candidate: Candidate = {
    ...definition,
    revision,
    status: "Saved",
    savedAt: stamp(now),
    change: changes.map((c) => c.title).join(" and ") || "Definition updated",
    changes,
    lastTest: skill.candidate?.lastTest ?? null,
    previousTest: skill.candidate?.previousTest ?? null,
  };
  return replace(state, {
    ...skill,
    name: draft.name.trim(),
    category: draft.category,
    owner: draft.owner,
    approver: draft.approver,
    candidate,
    history: [
      { title: `${version} · ${revision} saved`, actor: draft.owner, at: historyStamp(now), lifecycle: "Candidate · Definition saved" },
      ...skill.history,
    ],
  });
}

function describeChanges(published: Published | null, next: SkillDefinition): Array<{ title: string; detail: string }> {
  if (!published) return [{ title: "New skill", detail: "First candidate definition" }];
  const changes: Array<{ title: string; detail: string }> = [];
  if (hasStopRule(next.contract) && !hasStopRule(published.contract))
    changes.push({ title: "Missing-evidence stop", detail: "Explicit stop rule added" });
  if (next.contract.join("\n") !== published.contract.join("\n") && changes.length === 0)
    changes.push({ title: "Instruction contract", detail: "Wording updated" });
  if (next.inputSummary !== published.inputSummary) changes.push({ title: "Input schema", detail: next.inputSummary });
  if (next.outputSummary !== published.outputSummary) changes.push({ title: "Output schema", detail: next.outputSummary });
  return changes;
}

const SUITE: Array<{ name: string; total: number; outcome: string }> = [
  { name: "Citation grounding", total: 6, outcome: "All substantive claims cited" },
  { name: "Output format validation", total: 4, outcome: "PPTX / DOCX schemas valid" },
  { name: "Permission boundaries", total: 4, outcome: "Out-of-scope sources excluded" },
  { name: "Insufficient evidence", total: 4, outcome: "Clarification requested; no invented target" },
];

/**
 * Run the sandbox suite against the candidate's current revision. The simulated result follows the contract:
 * without a STOP rule the insufficient-evidence fixture invents a target and fails.
 */
export function runTests(state: SkillState, skillId: string, now: Date, durationSec = 42): { state: SkillState; testId: string } {
  const skill = state.skills.find((s) => s.id === skillId);
  if (!skill?.candidate) return { state, testId: "" };
  const candidate = skill.candidate;
  const stops = hasStopRule(candidate.contract);
  const testId = `TEST-${String(state.nextTest).padStart(3, "0")}`;
  const groups = SUITE.map((g) =>
    g.name === "Insufficient evidence" && !stops
      ? { name: g.name, passed: g.total - 1, total: g.total, outcome: "Target invented when baseline was missing" }
      : { ...g, passed: g.total },
  );
  const previous = candidate.lastTest;
  const regressions = previous?.groups.some((g) => g.name === "Insufficient evidence" && g.passed < g.total)
    ? [{ name: "Missing benefits baseline", fixture: "F-018", previousRun: previous.id, output: MISSING_EVIDENCE_OUTPUT, passed: stops }]
    : [];
  const run: TestRun = { id: testId, revision: candidate.revision, at: stamp(now), durationSec, fixtures: 18, groups, regressions };
  const passed = allPassed(run);
  return {
    testId,
    state: {
      ...replace(state, {
        ...skill,
        candidate: { ...candidate, status: passed ? "Tests passed" : "Saved", lastTest: run, previousTest: previous },
        history: [
          {
            title: `${candidate.version} · ${testId}`,
            actor: "System",
            at: historyStamp(now),
            lifecycle: `${passedCount(run)} / ${totalCount(run)} passed${passed ? "" : " · Baseline failure"}`,
          },
          ...skill.history,
        ],
      }),
      nextTest: state.nextTest + 1,
    },
  };
}

/** Why the candidate cannot be sent for publication review yet, or null. */
export function reviewBlocker(skill: Skill): string | null {
  const c = skill.candidate;
  if (!c) return "There is no candidate to release.";
  if (!c.lastTest || c.lastTest.revision !== c.revision) return "Rerun the sandbox suite on the saved revision first.";
  if (!allPassed(c.lastTest)) return "All sandbox tests must pass before publication review.";
  return null;
}

export function submitForReview(state: SkillState, skillId: string, now: Date): SkillState {
  const skill = state.skills.find((s) => s.id === skillId);
  if (!skill?.candidate || reviewBlocker(skill)) return state;
  return replace(state, {
    ...skill,
    candidate: { ...skill.candidate, status: "In review" },
    history: [
      { title: `${skill.candidate.version} submitted`, actor: skill.owner, at: historyStamp(now), lifecycle: "Pending independent approval" },
      ...skill.history,
    ],
  });
}

export type ReleaseGate = { name: string; result: string; ok: boolean };

export function releaseGates(skill: Skill): ReleaseGate[] {
  const c = skill.candidate;
  const test = c?.lastTest;
  return [
    { name: "Definition review", result: `${skill.approver} reviewed ${c?.revision ?? "—"}`, ok: c?.status === "In review" },
    {
      name: "Sandbox suite",
      result: test ? `${test.id} · ${passedCount(test)} / ${totalCount(test)} passed` : "Not run",
      ok: Boolean(c && test && test.revision === c.revision && allPassed(test)),
    },
    {
      name: "Role separation",
      result: `${skill.owner} author ${skill.owner === skill.approver ? "=" : "≠"} ${skill.approver} approver`,
      ok: skill.owner !== skill.approver,
    },
    {
      name: "Evidence policy",
      result: c && hasStopRule(c.contract) ? "Missing-evidence stop rule verified" : "Missing-evidence stop rule absent",
      ok: Boolean(c && hasStopRule(c.contract)),
    },
  ];
}

/** Release the candidate: it becomes the published version; the old one is retained for run provenance. */
export function publishCandidate(state: SkillState, skillId: string, note: string, now: Date): { state: SkillState; releaseId: string } {
  const skill = state.skills.find((s) => s.id === skillId);
  const c = skill?.candidate;
  if (!skill || !c || !releaseGates(skill).every((g) => g.ok) || note.trim().length < 10) return { state, releaseId: "" };
  const releaseId = `PUB-${skill.code.replace(/^SK-/, "")}-${c.version.replace(/\D/g, "")}`;
  const lastTest = c.lastTest;
  const published: Published = { ...definitionOf(c), approvedBy: skill.approver, publishedOn: day(now), releaseId };
  const at = historyStamp(now);
  const history: HistoryEvent[] = [
    {
      title: `${c.version} published`,
      actor: skill.approver,
      at,
      lifecycle: `Active · ${lastTest ? `${passedCount(lastTest)} / ${totalCount(lastTest)} tests passed` : "Released"}`,
    },
    ...(skill.published ? [{ title: `${skill.published.version} superseded`, actor: skill.approver, at, lifecycle: "Retained for run provenance" }] : []),
    ...skill.history,
  ];
  return { releaseId, state: replace(state, { ...skill, published, candidate: null, history }) };
}

// --- sample data ---------------------------------------------------------------------------------------------------

function sampleDefinition(version: string, fields: Partial<SkillDefinition> & Pick<SkillDefinition, "summary" | "inputSummary" | "outputSummary" | "formats">): SkillDefinition {
  return {
    version,
    contract: [fields.summary],
    inputs: fields.inputSummary.split(" · ").map((name) => ({
      name: name.toLowerCase().replace(/\s+/g, "_"),
      type: "string",
      rule: "Required",
      required: true,
    })),
    outputs: fields.outputSummary.split(" · ").map((name) => ({ name, contract: "Defined in the contract", validation: "Schema check" })),
    missingEvidence: "If required evidence is absent, ask for it or label the result as an assumption.",
    fixture: "Illustrative sandbox fixture",
    permittedRoles: "Engagement lead, Contributor · Scoped engagement only",
    ...fields,
  };
}

const ROADMAP_V21_CONTRACT = [
  "ROLE: Evidence-led transformation advisor. Retrieve approved practices and permitted engagement evidence. Propose phased actions with accountable owners and measurable gates.",
  "Cite every substantive claim or label it as an assumption. Produce a 12-slide PPTX and a 6-page DOCX for independent human review.",
];

const ROADMAP_IO: Pick<SkillDefinition, "inputs" | "outputs" | "missingEvidence" | "fixture"> = {
  inputs: [
    { name: "brief", type: "string", rule: "Minimum 30 characters · Objective and scope required", required: true },
    { name: "sources", type: "Source[]", rule: "Permitted, indexed sources · At least 1 required", required: true },
    { name: "horizon_days", type: "integer", rule: "30–365 · Default: 90", required: true },
    { name: "baseline", type: "Measure[]", rule: "Optional; missing benefits baseline triggers clarification", required: false },
  ],
  outputs: [
    { name: "PPTX roadmap", contract: "12 slides · Phases, owners, gates", validation: "Required sections & citations" },
    { name: "DOCX recommendations", contract: "6 pages · Evidence & assumptions", validation: "Claim-to-source coverage" },
    { name: "Evidence register", contract: "Source IDs, versions and locators", validation: "Permission inheritance" },
  ],
  missingEvidence: "If a quantitative baseline is absent, ask for clarification or mark benefits directional. Never invent a target.",
  fixture: "brief: Shared services redesign · horizon_days: 90 · sources: [LP-016 v3.2, NS discovery] · baseline: []",
};

const TEST_062: TestRun = {
  id: "TEST-062",
  revision: "C-008-22a",
  at: "08 Oct, 09:12",
  durationSec: 41,
  fixtures: 18,
  groups: [
    { name: "Citation grounding", passed: 6, total: 6, outcome: "All substantive claims cited" },
    { name: "Output format validation", passed: 4, total: 4, outcome: "PPTX / DOCX schemas valid" },
    { name: "Permission boundaries", passed: 4, total: 4, outcome: "Out-of-scope sources excluded" },
    { name: "Insufficient evidence", passed: 3, total: 4, outcome: "Target invented when baseline was missing" },
  ],
  regressions: [],
};

function published(definition: SkillDefinition, approvedBy: string, publishedOn: string, code: string): Published {
  return { ...definition, approvedBy, publishedOn, releaseId: `PUB-${code}-${definition.version.replace(/\D/g, "")}` };
}

export function sampleState(): SkillState {
  const roadmap: Skill = {
    id: "sk-008",
    code: "SK-008",
    name: "Roadmap builder",
    category: "Transformation",
    owner: "Maya Patel",
    approver: "Priya Shah",
    pinnedRun: "Northstar RUN-118",
    published: published(
      {
        ...sampleDefinition("v2.1", {
          summary: ROADMAP_V21_CONTRACT[0],
          inputSummary: "Brief · Sources · Horizon days · Baseline",
          outputSummary: "PPTX roadmap · DOCX recommendations · Evidence register",
          formats: "PPTX + DOCX",
        }),
        contract: ROADMAP_V21_CONTRACT,
        ...ROADMAP_IO,
      },
      "Priya Shah",
      "06 Oct 2026",
      "008",
    ),
    candidate: {
      ...sampleDefinition("v2.2", {
        summary: "Retrieve permitted sources, propose phased actions with accountable owners, and stop when the benefits baseline is missing.",
        inputSummary: "Brief · Sources · Horizon days · Baseline",
        outputSummary: "PPTX roadmap · DOCX recommendations · Evidence register",
        formats: "PPTX + DOCX",
      }),
      contract: [
        ROADMAP_V21_CONTRACT[0],
        "STOP: When the benefits baseline is missing, ask for evidence. Never invent a quantified target.",
        ROADMAP_V21_CONTRACT[1],
      ],
      ...ROADMAP_IO,
      revision: "C-008-22b",
      status: "Saved",
      savedAt: "08 Oct, 10:20",
      change: "Stricter baseline stop and named-owner checks",
      changes: [
        { title: "Missing-evidence stop", detail: "Explicit baseline request added" },
        { title: "Accountable-owner check", detail: "Require named pilot owner" },
        { title: "Evidence policy", detail: "Source permission inheritance retained" },
      ],
      lastTest: TEST_062,
      previousTest: null,
    },
    history: [
      { title: "v2.2 · C-008-22b saved", actor: "Maya Patel", at: "08 Oct 10:20", lifecycle: "Candidate · Stop rule corrected" },
      { title: "v2.2 submitted", actor: "Maya Patel", at: "08 Oct 09:18", lifecycle: "Pending independent approval" },
      { title: "v2.2 · TEST-062", actor: "System", at: "08 Oct 09:12", lifecycle: "17 / 18 passed · Baseline failure" },
      { title: "v2.1 published", actor: "Priya Shah", at: "06 Oct 15:10", lifecycle: "Active · 18 / 18 tests passed" },
      { title: "v2.0 superseded", actor: "Priya Shah", at: "06 Oct 15:10", lifecycle: "Retained for run provenance" },
    ],
  };

  type SampleSkill = Pick<Skill, "name" | "category" | "owner" | "approver"> &
    Pick<SkillDefinition, "version" | "summary" | "inputSummary" | "outputSummary" | "formats"> & { n: number; publishedOn: string };
  const simple = ({ n, name, category, owner, approver, version, publishedOn, ...text }: SampleSkill): Skill => {
    const code = String(n).padStart(3, "0");
    return {
      id: `sk-${code}`,
      code: `SK-${code}`,
      name,
      category,
      owner,
      approver,
      pinnedRun: "",
      published: published(sampleDefinition(version, text), approver, publishedOn, code),
      candidate: null,
      history: [{ title: `${version} published`, actor: approver, at: publishedOn.slice(0, 6), lifecycle: "Active" }],
    };
  };

  const discovery = simple({
    n: 3, name: "Discovery synthesis", category: "Discovery", owner: "Sam Rivera", approver: "Priya Shah",
    version: "v1.6", publishedOn: "30 Sep 2026", formats: "DOCX",
    summary: "Summarize permitted interviews and documents into themes, implications and explicit evidence gaps. Do not infer unsupported client facts.",
    inputSummary: "Discovery notes · Brief · Permitted source set",
    outputSummary: "DOCX synthesis · Citation-linked themes",
  });
  const operating = simple({
    n: 5, name: "Operating model advisor", category: "Operating model", owner: "Maya Patel", approver: "Sam Rivera",
    version: "v3.0", publishedOn: "22 Sep 2026", formats: "PPTX + DOCX",
    summary: "Compare the current operating model with approved practices and recommend target-state options with owners.",
    inputSummary: "Brief · Current-state evidence · Permitted source set",
    outputSummary: "PPTX options deck · DOCX rationale",
  });
  const governance = simple({
    n: 6, name: "Governance designer", category: "Governance", owner: "Priya Shah", approver: "Alex Chen",
    version: "v1.4", publishedOn: "15 Sep 2026", formats: "PPTX",
    summary: "Design decision forums, cadences and escalation paths from approved governance practices.",
    inputSummary: "Brief · Stakeholder map",
    outputSummary: "PPTX governance model",
  });
  const evidence = simple({
    n: 9, name: "Evidence checker", category: "Evidence", owner: "Sam Rivera", approver: "Priya Shah",
    version: "v2.2", publishedOn: "12 Sep 2026", formats: "DOCX",
    summary: "Check every claim in a draft against permitted sources and flag unsupported statements.",
    inputSummary: "Draft document · Permitted source set",
    outputSummary: "DOCX evidence report",
  });
  const storyteller = simple({
    n: 11, name: "Executive storyteller", category: "Storytelling", owner: "Alex Chen", approver: "Maya Patel",
    version: "v1.9", publishedOn: "05 Sep 2026", formats: "PPTX",
    summary: "Turn approved findings into an executive storyline with one message per slide.",
    inputSummary: "Findings · Audience",
    outputSummary: "PPTX executive summary",
  });

  operating.candidate = {
    ...sampleDefinition("v3.1", {
      summary: operating.published!.summary,
      inputSummary: operating.published!.inputSummary,
      outputSummary: operating.published!.outputSummary,
      formats: "PPTX + DOCX",
    }),
    contract: [operating.published!.summary, "STOP: When current-state evidence is missing, ask for it before proposing options.", "REVIEW: Human approval before export."],
    revision: "C-005-31a",
    status: "In testing",
    savedAt: "07 Oct, 16:40",
    change: "Current-state evidence stop",
    changes: [{ title: "Missing-evidence stop", detail: "Ask for current-state evidence" }],
    lastTest: null,
    previousTest: null,
  };
  evidence.candidate = {
    ...sampleDefinition("v2.3", {
      summary: evidence.published!.summary,
      inputSummary: evidence.published!.inputSummary,
      outputSummary: evidence.published!.outputSummary,
      formats: "DOCX",
    }),
    revision: "C-009-23a",
    status: "Draft definition",
    savedAt: "06 Oct, 11:05",
    change: "Draft: stricter unsupported-claim wording",
    changes: [{ title: "Instruction contract", detail: "Draft wording" }],
    lastTest: null,
    previousTest: null,
  };

  return { skills: [roadmap, discovery, operating, governance, evidence, storyteller], nextTest: 63, nextSkill: 12 };
}
