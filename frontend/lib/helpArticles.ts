// Help content shown under /help. Static guidance for the workbench's own workflows.

export type HelpArticle = {
  slug: string;
  title: string;
  category: "Engagement setup" | "Conversations & skills" | "Deliverables & review" | "Security & permissions";
  minutes: number;
  summary: string;
  steps: Array<{ heading: string; body: string }>;
  note?: { title: string; body: string };
  action?: { label: string; href: string };
};

export const HELP_CATEGORIES: Array<{ name: HelpArticle["category"]; blurb: string }> = [
  { name: "Engagement setup", blurb: "Brief, sources and access" },
  { name: "Conversations & skills", blurb: "Grounding and generation" },
  { name: "Deliverables & review", blurb: "Versions, comments and export" },
  { name: "Security & permissions", blurb: "Classification and retention" },
];

export const HELP_ARTICLES: HelpArticle[] = [
  {
    slug: "resolve-an-unsupported-claim",
    title: "Resolve an unsupported benefits claim",
    category: "Deliverables & review",
    minutes: 4,
    summary:
      "Add a permitted source or label the claim as an assumption, then rerun evidence checks before submitting the next version.",
    steps: [
      {
        heading: "1 / Inspect the flagged claim",
        body: "Open the review and look at its evidence checks. The evidence register shows the source locator, classification and affected artifact version for each claim.",
      },
      {
        heading: "2 / Add evidence or label the assumption",
        body: "Use approved practices and engagement documents. A playbook can support sequencing, but not a client-specific cost-reduction target. Remove the number or attach a baseline validated by the sponsor. Do not invent a baseline.",
      },
      {
        heading: "3 / Address comments and resubmit",
        body: "Mark each reviewer comment as addressed, describe what you changed and submit the revised draft. Approval is version-specific: approval of one version does not apply to the next.",
      },
    ],
    note: {
      title: "Never work around a source permission",
      body: "If a source is not in your engagement scope, request access from its owner. A pasted excerpt does not grant permission.",
    },
    action: { label: "Open your reviews", href: "/reviews" },
  },
  {
    slug: "why-is-export-locked",
    title: "Why is export locked?",
    category: "Deliverables & review",
    minutes: 3,
    summary: "Approval applies to one artifact version. Open comments or a new version require a fresh review.",
    steps: [
      {
        heading: "Check the Export step",
        body: "Open the engagement and select Export in the stepper. Each artifact lists its version, review state and whether export is available.",
      },
      {
        heading: "Clear the blockers",
        body: "Open the review that is named as a blocker. The owner addresses every comment and resubmits; the assigned reviewer then approves that version.",
      },
      {
        heading: "Download",
        body: "When every reviewed artifact is approved, Download PPTX and Download DOCX become available on the Export step and in Deliverables.",
      },
    ],
    note: {
      title: "Administrators cannot override content gates",
      body: "An administrator can route a review to another reviewer, but cannot approve an artifact or release an unapproved version.",
    },
  },
  {
    slug: "create-an-engagement",
    title: "Create an engagement and write a grounded brief",
    category: "Engagement setup",
    minutes: 3,
    summary: "Set the brief and access boundary before starting an advisory conversation.",
    steps: [
      {
        heading: "Create the engagement",
        body: "From Engagements choose New engagement. Give it a descriptive name, the organization, a brief of at least 30 characters and a security classification.",
      },
      {
        heading: "Complete the brief",
        body: "Open the Brief step to add the sponsor objective, scope and success measures. Distinguish objectives from unvalidated assumptions.",
      },
      {
        heading: "Attach sources",
        body: "On the Sources tab upload engagement documents and add approved practices from the library. Only these sources are used in conversations.",
      },
    ],
    action: { label: "New engagement", href: "/engagements/new" },
  },
  {
    slug: "invite-an-engagement-contributor",
    title: "Invite an engagement contributor",
    category: "Engagement setup",
    minutes: 2,
    summary: "The engagement lead adds existing organization accounts and chooses their role.",
    steps: [
      {
        heading: "Open Manage access",
        body: "On the engagement, choose Manage access (or the Team tab). Only the engagement lead sees the invitation form.",
      },
      {
        heading: "Choose a role",
        body: "Contributors draft and upload. Practice advisors draft and cite. Independent reviewers comment and approve. Viewers read permitted content only.",
      },
      {
        heading: "A second reviewer is optional",
        body: "An author can review and approve their own drafts; that is recorded as a self-review. Add an independent reviewer when you want a second pair of eyes.",
      },
    ],
  },
  {
    slug: "start-a-conversation-and-create-drafts",
    title: "Start a conversation and create drafts",
    category: "Conversations & skills",
    minutes: 4,
    summary: "Ask a question grounded in the engagement's sources, then turn the answer into PPTX and DOCX drafts.",
    steps: [
      {
        heading: "Pick the skill",
        body: "The active skill is shown beside the conversation. Change it there, or choose Run in engagement from the Skills page.",
      },
      {
        heading: "Ask and refine",
        body: "Ask for advice and follow-ups. The Sources in scope panel lists exactly which documents and practices can be cited.",
      },
      {
        heading: "Create drafts",
        body: "Choose Create PPTX + DOCX drafts. When a plan is ready, approve it to start generation, then open View artifacts.",
      },
    ],
  },
  {
    slug: "trace-a-citation-back-to-its-source",
    title: "Trace a citation back to its source",
    category: "Deliverables & review",
    minutes: 3,
    summary: "Use the evidence register to see which claim is supported by which source.",
    steps: [
      {
        heading: "Open the evidence register",
        body: "In Deliverables choose the Evidence register tab. Each claim lists its slide, source and whether it is cited or unsupported.",
      },
      {
        heading: "Check slide by slide",
        body: "On the PowerPoint tab, the panel under the slide shows the evidence linked to the slide you are viewing.",
      },
    ],
  },
  {
    slug: "classification-and-retention",
    title: "Classification and retention",
    category: "Security & permissions",
    minutes: 3,
    summary: "How engagement content is classified, who can see it and how long it is kept.",
    steps: [
      {
        heading: "Engagement-scoped access",
        body: "Members see only the content of engagements they belong to. Membership does not grant access to restricted sources, which need their data owner's approval.",
      },
      {
        heading: "Retention",
        body: "Engagements keep their content for 180 days after close by default. An administrator can change the period with a recorded reason.",
      },
      {
        heading: "Administrative access",
        body: "The administrator role manages routing, retention and archiving. It does not grant access to engagement content.",
      },
    ],
  },
];

export function findHelpArticle(slug: string): HelpArticle | undefined {
  return HELP_ARTICLES.find((article) => article.slug === slug);
}
