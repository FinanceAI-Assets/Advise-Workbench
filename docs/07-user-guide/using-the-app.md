# Using the app

A walkthrough from an empty project to a generated document. It assumes the app is running (see [../SETUP.md](../SETUP.md)).

## The flow in one view

1. **Create a project.**
2. **Upload source documents.**
3. **Tell Sheldon what you need.** Sheldon is the assistant in the project's chat.
4. **Answer its questions and confirm the plan.**
5. **The run generates the deliverable** and checks it.
6. **Review and approve.**

## 1. Create a project

Open http://localhost:3000, sign in, and choose **New project**. Each project has its own documents, chat, runs and wiki.

## 2. Upload source documents

On the project page, use **Project Documents** in the right-hand panel. Accepted formats: `.txt`, `.md`, `.csv`, `.json`, `.pdf`, `.docx`, `.pptx`, `.xlsx`, `.xls`, up to 50 MB each.

Upload before you confirm a plan. The generated content is expected to cite these documents, and figures that cannot be traced to them are flagged.

## 3. Tell Sheldon what you need

Type into the box that reads "Chat with Sheldon…". Say what you want, for whom, and in which format. Name the format once and clearly, for example "PPTX only" or "DOCX only"; the first format you state is the one the plan uses.

A request that works well:

```
Build a 10-slide executive presentation for Northwind Manufacturing's P2P transformation
program. Cover the current-state pain points with quantified metrics, the transformation
pillars, 90-day quick wins, the 18-month roadmap and expected benefits. PPTX only.
Put a (source: document name) citation next to every figure, and end with a
"Sources and assumptions" slide.
```

## 4. Answer questions and confirm the plan

Sheldon usually asks for three things if they are missing: the client and the problem, the audience and the decision they must make, and two or three key messages. It then proposes a storyline and, when it has enough, a plan.

Confirm the plan, or say "Build it", to start the run.

Replies can take one to two minutes. While Sheldon works, the chat shows the current step (for example "Sheldon: Writing the reply…"). If answering a plan decision or confirming a plan shows "fetch aborted", the reply is still being saved: wait about 30 seconds and refresh the page. Do not send it again.

## 5. The run

A run goes through these steps, shown in the right-hand panel:

| Step | What happens |
|---|---|
| Assemble context | Your documents, the project wiki and memory are gathered |
| Extract process model | Steps, roles and decisions are pulled from the sources |
| Plan | The order and outline of deliverables are decided |
| Generate | The document is written and built as a file |
| Quality review | Structure and content are scored and repaired if needed |
| Guardrails | Source grounding, references, brand and style are checked |
| Visual QA | The rendered pages are inspected for layout problems |

A deck typically takes 10 to 20 minutes. If a check fails, the run repairs the document and tries again, up to three times.

## 6. Review and approve

When the run reaches **review ready**, open the artifacts, read the quality and evidence findings, and give final approval. Generated files are also kept on disk under `workspace/<project id>/runs/<run id>/`.

## What can be produced

| Deliverable | Formats |
|---|---|
| Standard operating procedure (SOP) | Word, PDF |
| RACI matrix | Excel, Word |
| Executive narrative | Word, PowerPoint, PDF |
| Process map | draw.io |
| Business requirements document | Word, PowerPoint, PDF |
| Approach note | Word |
| Finance transformation proposal | Word, PowerPoint, PDF |

## Sample material

`data/examples/northwind-p2p/` holds source documents for a fictional manufacturer and six ready-made requests (scenarios A to F) in `run-scenarios/README.md`. Scenario C, the executive deck, is the quickest first test.

## The wiki and the leading-practice library

- **Project wiki:** knowledge pages built from the project's documents, runs and chats. Sheldon draws on it when answering.
- **Leading-practice library:** reference material shared across all projects, such as templates and standards. Do not put client-confidential material there; every signed-in user can read it.
