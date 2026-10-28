# Guided view: the six-step project journey

A second way to work in a project, at `/v2/projects/<project id>`. The classic project page is unchanged and each page links to the other.

## Why

Problems seen while using the classic page:

- Nothing shows which step of the work you are in.
- A run starts from a chat message; there is no screen where the plan and format are confirmed.
- Asking for a Word document in chat produced a presentation.
- A failed run shows its reason only in the server log.

## The six steps

| Step | Purpose | Main action | Marked done when |
|---|---|---|---|
| 1. Brief | Tell Sheldon what is needed | Chat with Sheldon | You have written to Sheldon and no questions are open |
| 2. Sources | Give the documents the deliverable must be based on | Upload files | At least one document is uploaded |
| 3. Plan | Check the outline, choose the format, confirm | "Confirm plan and build" | A run exists |
| 4. Build | Watch the run | None (progress feed) | The run has reached review, failed or finished |
| 5. Review | See the checks, approve or send back | Approve / request changes | The run is approved |
| 6. Deliver | Download the files | Download | (Becomes the current step once the run is approved) |

The step bar is always visible. Each step shows `DONE`, `NOW`, `LATER` or a warning (for example no sources, or a failed run); any step can be opened at any time. The open step is kept in the address (`?step=plan`), so a link or a page refresh returns to the same place. Sheldon is available as a side panel from every step.

## What is different from the classic page

- **Format is a button, not a sentence.** In Plan, the chosen format is sent to Sheldon as an explicit instruction together with the confirmation.
- **Missing sources are flagged before the build**, because figures cannot be cited without them.
- **A failed run shows its reason** in Review, read from the run's `failed` event, with the next action.
- **Build has pause, resume and stop**, and **Review has the evidence list** (accept or reject each claim) before approval.

## Code

| File | Role |
|---|---|
| `frontend/app/v2/projects/[pid]/page.tsx` | Route |
| `frontend/features/journey/steps.ts` | Step list and the rules for done / now / later (pure functions, tested in `steps.test.ts`) |
| `frontend/features/journey/JourneyStudio.tsx` | The view: step bar, step header and one component per step |
| `frontend/hooks/useProjectStudio.ts` | All project state and actions (conversation, documents, run, events). Taken out of `ProjectStudioUnified.tsx`, so the classic and guided views share it |

No backend change: the guided view uses the same API calls as the classic page.

## Verified

- Type check, lint, unit tests (20 files, 77 tests) and production build pass.
- Browser check on a new empty project: all six steps open, the suggested step is Brief, the format choice is marked, the confirm button is disabled until there is a brief, and the layout works at phone width.

## Not done yet

| Item | Note |
|---|---|
| A full run through the guided view with a real model | Only the empty-project state was checked in a browser. Build, Review and Deliver with real run data are untested |
| Outline editor inside the Plan step | The outline can be edited and saved from the Ask Sheldon panel ("Edit outline" under the plan); the Plan step itself shows it read-only |
| Re-run from a stage in Review | Not built. Evidence accept / reject is in the Review step |
| Moving the other pages into `features/` | Only `features/journey/` exists |
| Style audit | `npm run ui:style-audit` fails on 176 older violations in existing files; the new files add none |
| Making the guided view the default | Decide after a full run has been done through it |
