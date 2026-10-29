# Advise Workbench: how to run it

A short guide: what runs, what you need, how to start it, and one complete example from sample input files to generated output files. Full detail is in [docs/SETUP.md](docs/SETUP.md) and [docs/07-user-guide/using-the-app.md](docs/07-user-guide/using-the-app.md).

## 1. The services

One command starts all of them: `./scripts/run_agent.sh`.

| Service | Address | What it does | Needed |
|---|---|---|---|
| Frontend | http://localhost:3000 | The web app you use | Always |
| Backend | http://127.0.0.1:8000 (API reference at `/docs`) | API, LangGraph run and conversation graphs, document agents, quality checks | Always |
| Claude CLI bridge | http://127.0.0.1:8787 | Lets the backend use a signed-in Claude Code CLI instead of an API key | Only in bridge mode (see section 3) |
| OpenObserve | http://localhost:5080 | Monitoring: traces, metrics and logs | Optional |

Data stays on your machine: the database is `advise_workbench.db` and all uploaded and generated files are under `workspace/`.

## 2. Prerequisites

| Tool | Version | Install on macOS |
|---|---|---|
| Python | 3.11 or newer | `brew install python@3.11` |
| Node.js and npm | 18 or newer | `brew install node` |
| git | any | `xcode-select --install` |

Access to a language model, one of:

| Option | What you need |
|---|---|
| Claude Code subscription (no API key) | `npm install -g @anthropic-ai/claude-code`, then run `claude` once and sign in |
| Anthropic API key | A key that starts with `sk-ant-` |
| An OpenAI-style service | Its address, a model name and a key |

Optional: LibreOffice (`brew install --cask libreoffice`) gives better visual checks of decks and documents.

## 3. First-time set-up

From the repository folder:

```bash
cp .env.example .env
```

Open `.env` and set the lines for your model option:

| Option | Lines in `.env` |
|---|---|
| Claude Code through the bridge | `ANTHROPIC_BASE_URL=http://127.0.0.1:8787` and `ANTHROPIC_API_KEY=not-used-cli-bridge` |
| Claude Code directly | `LLM_PROVIDER=claude_cli` |
| Anthropic API key | `ANTHROPIC_API_KEY=<your key>` |
| OpenAI-style service | `LLM_PROVIDER=openai_compatible`, `LLM_MODEL=<model>`, `LLM_API_KEY=<key>`, `LLM_BASE_URL=<address>` |

Then let the start script check and install everything:

```bash
./scripts/run_agent.sh --check --fix
```

It creates the Python environment (`.venv`), installs the backend and frontend packages, generates a `JWT_SECRET`, and prints `PASS`, `WARN`, `FIXED` or `FAIL` for each check. A `FAIL` line shows the command that fixes it.

Optional monitoring, once:

```bash
./scripts/openobserve.sh setup
```

## 4. Start and stop

```bash
./scripts/run_agent.sh
```

Wait for `Ready.` and the list of addresses, then open http://localhost:3000. Press `Ctrl+C` in that terminal to stop everything. Logs are in `.run/`.

Sign in with any email and password; the first sign-in creates the account.

## 5. End to end: sample input to output files

The sample is a fictional client, Northwind Manufacturing, improving its procure-to-pay process. The input files are in `data/examples/northwind-p2p/source-documents/`.

### Step 1: create a project

Open http://localhost:3000, sign in, choose **New project** and give it a name, for example "Northwind P2P".

### Step 2: upload the sample input

In the project, open **Project Documents** in the right-hand panel and upload these three files:

| File | What it contains |
|---|---|
| `01_procure_to_pay_current_state.md` | Process steps, roles, systems, risks, metrics |
| `02_discovery_workshop_notes.txt` | Stakeholder quotes, pain points, action items |
| `05_baseline_metrics_memo.md` | Baseline figures, targets, benefits case |

Wait until each file shows as parsed.

### Step 3: ask for the deliverable

Paste this into the chat box ("Chat with Sheldon…"):

```
Build a 10-slide executive presentation for Northwind Manufacturing's P2P transformation
program. Cover: situation/complication, current-state pain points with quantified metrics,
transformation pillars, 90-day quick wins, 18-month roadmap, and expected benefits.
PPTX only. Cite sources from uploaded documents.
```

### Step 4: answer Sheldon and start the run

Sheldon may ask about the audience, the decision they must make, and the key messages. Answer briefly, for example: "Audience is the CFO. Focus on cost savings and efficiency. Use sensible defaults for the rest."

When Sheldon shows the slide structure and says it is ready, type:

```
go
```

Each reply takes about one minute with Claude Code; the chat shows the step Sheldon is on.

### Step 5: wait for the run

The right-hand panel shows progress. A run goes through six phases:

| Phase | What happens |
|---|---|
| prepare | The run is loaded and permissions are checked |
| context | The plan, settings and a digest of the conversation are assembled |
| generate | Agents plan, write and build the file |
| evaluate | Quality, guardrail, evidence and visual checks |
| remember | What the project should remember from the run is saved |
| finalize | The run is marked ready for review |

A deck takes 10 to 20 minutes with Claude Code. If a check fails, the run repairs the document and tries again, up to three times.

### Step 6: get the output files

When the run reaches **review ready**, open the artifacts in the project page to preview and download them. The same files are on disk:

```
workspace/<project id>/runs/<run id>/
```

For this example the files to look at are:

| File | What it is |
|---|---|
| `output.pptx` | The deck |
| `deck.pdf` | The deck as a PDF |
| `qa_report.json`, `guardrail_report.json`, `evidence_claims.json` | Results of the quality, guardrail and evidence checks |
| `storyline.json`, `pptx_slides.json` | The storyline and slide content the deck was built from |

### Other deliverables

`data/examples/northwind-p2p/run-scenarios/README.md` has six ready-made requests (scenarios A to F): a full pack, an Excel RACI matrix, the deck above, a process map with a Word SOP, and more. For those, upload all the files in `source-documents/`.

## 6. What to expect

- **Speed:** with Claude Code, chat replies take about a minute and a deck run 10 to 20 minutes per attempt. An API key is faster.
- **Quality checks:** in test runs so far the generated deck has not passed every automatic check (visual and source-grounding checks in particular), so a run can end as failed after three attempts. The files written by each attempt are still in the run folder.
- **Restart:** if the backend stops during a run, start it again; the run continues from the last finished phase.
- **Redis messages at start-up:** "connection refused" lines about Redis are harmless on one machine.

## 7. Monitoring (optional)

With OpenObserve set up, open http://localhost:5080 and sign in with `OPENOBSERVE_USER` and `OPENOBSERVE_PASSWORD` from `.env`. **Traces** shows each chat turn and each run as a timeline with every model call. See [docs/06-deployment-operations/observability.md](docs/06-deployment-operations/observability.md).

## 8. If something goes wrong

| Symptom | Fix |
|---|---|
| A `FAIL` line from `run_agent.sh` | Run the command shown under it, or `./scripts/run_agent.sh --check --fix` |
| Sign-in says "Invalid credentials" on a new install | Set `AUTH_ALLOW_SELF_SIGNUP=true` in `.env` and restart |
| "Connection error" or "circuit breaker is open" in the chat | The bridge is not running: start with `./scripts/run_agent.sh` and wait a minute |
| `claude: command not found` | `npm install -g @anthropic-ai/claude-code` |
| A port is already in use | Stop the other program, or set `BACKEND_PORT`, `FRONTEND_PORT` or `BRIDGE_PORT` before the command |

More cases are in [docs/SETUP.md](docs/SETUP.md), section 7.
