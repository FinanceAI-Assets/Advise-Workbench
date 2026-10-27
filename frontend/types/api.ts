/** Shared API response shapes aligned with backend routes. */

export type ProjectRow = { id: string; name: string };
export type ProjectsListResponse = { items: ProjectRow[] };

export type EngagementStage = "Brief" | "Sources" | "Drafting" | "In review" | "Approved";

export type EngagementRow = {
  id: string;
  name: string;
  code: string;
  type: string;
  stage: EngagementStage;
  progress: number;
  owner: string;
  nextTask: string;
  dueDate: string;
};

export type EngagementStat = {
  id: string;
  label: string;
  value: number;
  helper: string;
  helperTone?: "default" | "warning" | "success";
};

export type NextAction = {
  id: string;
  title: string;
  description: string;
  due: string;
  actionLabel?: string;
  href?: string;
  icon: "comment" | "review";
};

export type NextActionBuckets = { needsAction: NextAction[]; upcoming: NextAction[]; completed: NextAction[] };

export type ActivityItem = {
  id: string;
  title: string;
  meta: string;
  detail?: string;
  kind?: string;
  icon: "deck" | "library";
};

export type EngagementStepStatus = "complete" | "in-progress" | "upcoming";
export type EngagementStepIcon = "number" | "cycle";

export type EngagementStep = {
  id: string;
  index: number;
  label: string;
  status: EngagementStepStatus;
  helper: string;
  icon?: EngagementStepIcon;
};

export type EngagementBrief = {
  updated: string;
  summary: string;
  context: string;
  sponsorObjective: string;
  scope: string;
  successMeasures: string;
  classification: string;
};

export type MilestoneStatus = "Complete" | "Drafting" | "Scheduled";

export type Milestone = {
  id: string;
  name: string;
  owner: string;
  target: string;
  status: MilestoneStatus;
};

export type TeamMember = {
  id: string;
  name: string;
  roleAndAccess: string;
  userId?: string;
  email?: string;
  role?: string;
  permission?: string;
  status?: string;
};

export type EvidenceSource = {
  id: string;
  label: string;
  value: string;
};

export type Deliverable = {
  id: string;
  name: string;
  meta: string;
  icon: "deck" | "doc" | "evidence";
  status?: string;
};

export type EngagementDetail = {
  id: string;
  code: string;
  name: string;
  subtitle: string;
  dateRange: string;
  lead: string;
  teamMemberCount: number;
  steps: EngagementStep[];
  tabCounts: { sources: number; deliverables: number; team: number };
  brief: EngagementBrief;
  milestones: Milestone[];
  teamMembers: TeamMember[];
  teamNote: string;
  evidenceSourceCount: number;
  evidenceSources: EvidenceSource[];
  evidenceWarning: { title: string; description: string } | null;
  deliverables: Deliverable[];
  clientOrg?: string;
  startDate?: string;
  targetClose?: string;
  stage?: EngagementStage;
  status?: string;
  retentionDays?: number;
  documents?: string[];
  practices?: Array<{ id: string; practiceId: string; title: string }>;
};

export type EngagementsPage = { items: EngagementRow[]; total: number; page: number; pageSize: number };

export type ExportArtifact = {
  id: string;
  name: string;
  version: string;
  review: string;
  export: string;
  runId: string | null;
  type: string;
};

export type ExportReadiness = { artifacts: ExportArtifact[]; ready: boolean; blockers: string[]; message: string };

export type PlatformRole = "user" | "admin";
export type AuthUser = {
  id: string;
  email: string;
  name: string;
  jobTitle: string;
  isAdmin: boolean;
  role: PlatformRole;
  canSwitchAdmin: boolean;
};

export type ConversationPhase = {
  label: string;
  description: string;
  citations: number[];
};

export type ConversationMessage = {
  id: string;
  role: "user" | "assistant";
  author: string;
  timestamp: string;
  badge?: string;
  body?: string;
  headline?: string;
  intro?: string;
  phases?: ConversationPhase[];
  evidenceGap?: { title: string; description: string } | null;
  // Raw message metadata from the backend (for example the choices Sheldon offers).
  metadata?: Record<string, unknown>;
};

export type EngagementContextSummary = {
  classification: string;
  name: string;
  description: string;
  lead: string;
  teamNote: string;
};

export type ActiveSkill = {
  name: string;
  version: string;
  meta: string;
  formats: string[];
};

export type PracticeContext = {
  name: string;
  meta: string;
  practiceHref: string;
};

export type RecentConversationItem = {
  id: string;
  label: string;
  active?: boolean;
};

export type EvidenceMatch = {
  id: string;
  index: number;
  relevance: number;
  title: string;
  source: string;
  quote: string;
  attribution: string;
};

export type ConversationDetail = {
  engagementId: string;
  engagementCode: string;
  engagementName: string;
  title: string;
  subtitle: string;
  scopeSummary: string;
  context: EngagementContextSummary;
  skill: ActiveSkill;
  practice: PracticeContext;
  recent: RecentConversationItem[];
  messages: ConversationMessage[];
  evidence: EvidenceMatch[];
  evidenceShown: number;
  evidenceTotal: number;
  sourcesInScope: number;
};

export type ArtifactFileType = "pptx" | "docx" | "evidence";
export type ArtifactStatus = "Changes requested" | "Draft" | "Approved";

export type EngagementFile = {
  id: string;
  type: ArtifactFileType;
  name: string;
  meta: string;
  status?: ArtifactStatus;
};

export type VersionHistoryEntry = {
  id: string;
  version: string;
  current?: boolean;
  meta: string;
};

export type SlidePhase = { label: string; title: string; description: string };

export type Slide = {
  id: string;
  index: number;
  title: string;
};

export type SlideDetail = {
  breadcrumb: string;
  headline: string;
  phases: SlidePhase[];
  sources: string;
  footerMeta: string;
  pageLabel: string;
};

export type SlideEvidenceLink = {
  id: string;
  index: number;
  label: string;
  description: string;
  icon: "library" | "doc";
  verified: boolean;
};

export type DocSection = { heading: string; body: string };

export type WordArtifactPreview = {
  breadcrumb: string;
  title: string;
  meta: string;
  sections: DocSection[];
  footerMeta: string;
  pageLabel: string;
};

export type DeliverablesDetail = {
  engagementId: string;
  engagementName: string;
  title: string;
  subtitle: string;
  tabCounts: { all: number; powerpoint: number; word: number; evidenceRegister: number };
  files: EngagementFile[];
  versions: VersionHistoryEntry[];
  pptx: {
    name: string;
    versionLabel: string;
    status: ArtifactStatus;
    slides: Slide[];
    activeSlideIndex: number;
    slideDetail: SlideDetail;
    evidenceLinks: SlideEvidenceLink[];
  };
  docx: {
    name: string;
    status: ArtifactStatus;
    versionLabel: string;
    preview: WordArtifactPreview;
    citationSummary: string;
    exportWarning: { title: string; description: string } | null;
    generatedFootnote: string;
  };
};

export type PracticeCategory = { id: string; label: string; count: number };

export type PracticeCardSummary = {
  id: string;
  title: string;
  description: string;
  status: "Approved";
  maturity: string;
  category: string;
  versionLabel: string;
};

export type PracticeDetail = {
  id: string;
  code: string;
  title: string;
  description: string;
  status: "Approved";
  versionLabel: string;
  maturity: string;
  recommendedWhen: string;
  coreGuidance: string[];
  sourceAttribution: string;
  practiceOwner: string;
  approvedMeta: string;
  sourceQuality: string;
};

export type LPLibraryDetail = {
  totalPractices: number;
  categories: PracticeCategory[];
  activeCategoryId: string;
  matchingCount: number;
  cards: PracticeCardSummary[];
  practices: Record<string, PracticeDetail>;
};

export type SkillCardSummary = {
  id: string;
  name: string;
  description: string;
  versionLabel: string;
  formats: string;
  published: boolean;
};

export type SkillDetail = {
  id: string;
  code: string;
  name: string;
  versionLabel: string;
  category: string;
  evidenceRequired: boolean;
  description: string;
  howItWorks: string[];
  requiredInputs: string;
  expectedOutputs: string;
  evidencePolicy: string;
  maintainedBy: string;
  lastPublished: string;
  runInEngagement: string;
};

export type SkillsDetail = {
  totalPublished: number;
  cards: SkillCardSummary[];
  skills: Record<string, SkillDetail>;
};

export type ReviewCommentStatus = "Open" | "Resolved";

export type ReviewComment = {
  id: string;
  title: string;
  status: ReviewCommentStatus;
  attribution: string;
  body: string;
};

export type EvidenceCheckResult = "Passed" | "Gap";

export type EvidenceCheckRow = {
  id: string;
  check: string;
  result: EvidenceCheckResult;
  resultLabel: string;
  action: string;
};

export type ApprovalEvent = {
  id: string;
  title: string;
  attribution: string;
  icon: "check" | "comment" | "edit";
};

export type ReviewDetail = {
  id: string;
  code: string;
  engagementName: string;
  artifactName: string;
  versionLabel: string;
  owner: string;
  reviewer: string;
  dueDate: string;
  steps: EngagementStep[];
  slide: SlideDetail;
  slideCommentCount: number;
  evidenceChecksRunMeta: string;
  evidenceChecks: EvidenceCheckRow[];
  comments: ReviewComment[];
  openCount: number;
  resolvedCount: number;
  approverName: string;
  approverRole: string;
  approvalStatus: string;
  approvalTimeline: ApprovalEvent[];
};

// --- Admin console -------------------------------------------------------

export type AdminStatTone = "default" | "warning" | "success";

export type AdminStat = {
  id: string;
  label: string;
  value: string;
  helper: string;
  helperTone?: AdminStatTone;
};

export type PendingApprovalRow = {
  id: string;
  item: string;
  typeVersion: string;
  assignedTo: string;
  due: string;
  state: string;
};

export type IngestionHealthItem = {
  id: string;
  title: string;
  meta: string;
  status: "Healthy" | "Attention";
  icon: "library" | "upload" | "plug";
};

export type RiskQueueRow = {
  id: string;
  riskScope: string;
  severity: "High" | "Medium" | "Low";
  owner: string;
  control: string;
};

export type ControlAuditItem = {
  id: string;
  label: string;
  state: string;
};

export type AdminOverviewDetail = {
  stats: AdminStat[];
  pendingApprovals: PendingApprovalRow[];
  pendingApprovalsTotal: number;
  ingestionHealth: IngestionHealthItem[];
  ingestionUpdatedMeta: string;
  ingestionWarning: { title: string; description: string } | null;
  riskQueue: RiskQueueRow[];
  riskQueueOpenCount: number;
  riskQueueFootnote: string;
  controlsAudit: ControlAuditItem[];
  controlsAuditEvent: string;
};

export type AdminEngagementRow = {
  id: string;
  name: string;
  code: string;
  ownerAccess: string;
  classification: string;
  retention: string;
  deliverables: string;
  controlState: string;
};

export type SelectedEngagementMember = { id: string; name: string; role: string; permission: string };

export type SelectedEngagementDetail = {
  id: string;
  code: string;
  name: string;
  accessGroup: string;
  contentAccess: string;
  retentionPolicy: string;
  scheduledDisposition: string;
  members: SelectedEngagementMember[];
};

export type DeliverableLifecycleItem = {
  id: string;
  name: string;
  meta: string;
  state: string;
  icon: "deck" | "doc" | "evidence";
};

export type AdminEngagementsDetail = {
  tabCounts: { engagements: number; deliverables: number; retentionExceptions: number; exportRequests: number };
  matchingCount: number;
  totalCount: number;
  rows: AdminEngagementRow[];
  selected: SelectedEngagementDetail;
  deliverableLifecycle: DeliverableLifecycleItem[];
};

export type PracticeInventoryRow = {
  id: string;
  practiceSource: string;
  version: string;
  indexing: string;
  lifecycle: string;
};

export type IngestionJobDetail = {
  id: string;
  filename: string;
  meta: string;
  status: string;
  extractionMeta: string;
  indexValidationMeta: string;
  provenanceMeta: string;
  warning: { title: string; description: string } | null;
};

export type SourceQualityCheck = { id: string; label: string; state: string };

export type QualityReviewDetail = {
  id: string;
  code: string;
  title: string;
  versionLabel: string;
  approvalState: string;
  taxonomy: string;
  maturity: string;
  practiceOwner: string;
  approver: string;
  sourceQualityChecks: SourceQualityCheck[];
  warning: { title: string; description: string } | null;
  footnote: string;
};

/** One row of a library pipeline checklist: a gate or check, its result, and the supporting detail. */
export type LibraryCheckRow = { id: string; label: string; result: string; detail: string; tone: "ok" | "warn"; passed?: boolean };

export type LibraryNotice = { title: string; description: string };

export type LibraryField = { label: string; value: string };

export type ExtractedChunk = {
  id: string;
  code: string;
  page: number | null;
  section: string;
  tokens: number;
  quality: string;
  tone: "ok" | "warn";
  passageMeta: string;
  passage: string;
};

export type LibraryExtractionDetail = {
  subtitle: string;
  sourceHash: string;
  chunks: ExtractedChunk[];
  provenance: LibraryNotice;
  /** Set when the source had no readable text and is excluded from retrieval. */
  error?: LibraryNotice | null;
};

export type LibraryIndexValidationDetail = {
  subtitle: string;
  summary: string;
  checks: LibraryCheckRow[];
  inspection: LibraryField[];
  warning: LibraryNotice | null;
  retrievalChecks: LibraryCheckRow[];
};

export type LibraryCorrectionDraft = {
  assignee: string;
  due: string;
  sourceLocation: string;
  requiredCorrection: string;
  severity: string;
};

export type LibraryCorrectionRecord = {
  id: string;
  reason: string;
  assignee: string;
  status: string;
  requestedBy: string;
  requestedAt: string;
};

export type LibraryQualityGatesDetail = {
  practiceId?: string;
  title: string;
  subtitle: string;
  gates: LibraryCheckRow[];
  blocker: LibraryNotice | null;
  metadata: LibraryField[];
  correction: LibraryCorrectionDraft;
  // Present for uploaded sources; the sample walkthrough has no live review.
  review?: { id: string; state: string; reviewer: string; selfReview: boolean } | null;
  openCorrection?: LibraryCorrectionRecord | null;
  approvers?: Array<{ id: string; name: string }>;
  canSubmit?: boolean;
  canPublish?: boolean;
};

export type LibraryReleaseDetail = {
  practiceId: string;
  subtitle: string;
  gates: LibraryCheckRow[];
  notice: LibraryNotice;
  record: LibraryField[];
  published?: boolean;
  canPublish?: boolean;
  blockers?: string[];
};

export type AdminLibraryDetail = {
  pipelineSteps: EngagementStep[];
  practiceInventoryTotal: string;
  practiceInventory: PracticeInventoryRow[];
  latestIngestionJob: IngestionJobDetail;
  qualityReview: QualityReviewDetail;
  /** The practice the pipeline steps describe: an uploaded one, or the sample walkthrough's. */
  selectedPracticeId: string;
  /** "upload" when the steps show a real uploaded source; "sample" for the illustrative walkthrough. */
  pipelineSource: "upload" | "sample";
  // Pipeline tab content.
  extraction?: LibraryExtractionDetail;
  indexValidation?: LibraryIndexValidationDetail;
  qualityGates?: LibraryQualityGatesDetail;
  release?: LibraryReleaseDetail;
};

export type ReviewQueueRow = {
  id: string;
  itemReference: string;
  reviewer: string;
  type: string;
  state: string;
};

export type SelectedReviewGovernanceDetail = {
  id: string;
  code: string;
  title: string;
  riskLevel: string;
  badges: string[];
  artifactOwner: string;
  assignedApprover: string;
  riskDescription: string;
  warning: { title: string; description: string } | null;
  footnote: string;
};

export type PolicyControlItem = { id: string; label: string; state: string };

export type RoleAccessRow = { id: string; role: string; allowed: string; restricted: string };

export type AuditTrailEvent = { id: string; title: string; attribution: string; icon: "check" | "history" | "send" | "comment" };

export type AdminReviewsGovernanceDetail = {
  tabCounts: { reviewQueue: number; riskRegister: number; policies: number };
  queue: ReviewQueueRow[];
  selectedReview: SelectedReviewGovernanceDetail;
  policyControls: PolicyControlItem[];
  policyCode: string;
  exportPermissionsNote: string;
  roleAccess: RoleAccessRow[];
  auditTrail: AuditTrailEvent[];
};

export type RunRow = {
  id: string;
  status: string;
  created_at: string | null;
  instruction: string;
  tokens_input?: number | null;
  tokens_output?: number | null;
  tokens_cache_read?: number | null;
  tokens_cache_creation?: number | null;
  cost_usd?: number | null;
};

export type RunsListResponse = { items: RunRow[] };

export type RunEventItem = { id: number; event_type: string; payload: Record<string, unknown> };
export type RunEventsResponse = {
  run_id: string;
  status: string;
  plan?: unknown;
  items: RunEventItem[];
};

export type RunTask = {
  id: string;
  title: string;
  status: string;
  phase: string;
  started_at?: string | null;
  completed_at?: string | null;
  duration_ms?: number | null;
};

export type RunTasksResponse = {
  run_id: string;
  project_id: string;
  items: RunTask[];
};
