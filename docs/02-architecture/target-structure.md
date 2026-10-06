# Advise-Workbench: target structure and modularisation plan

## Context

The app (repo `Advise-Workbench`, local folder `advise-workbench`) works, but it is hard to read and heavy:

- **Backend is organised by technical layer, not by purpose.** `backend/app/services/` holds 108 files (39,663 lines) in one flat folder; `app/core/` holds 55 files mixing configuration, security and all document builders.
- **A few files carry too much.** `agents/subagents.py` 3,565 lines (all 8 agents), `api/projects/conversation.py` 2,838, `services/wiki_operations.py` 2,166, `services/run_worker.py` 2,020, `api/runs.py` 1,896, `services/tool_registry.py` 1,826, `agents/coordinator_execution.py` 1,790. The three coordinator files repeat the same helpers.
- **Prompts are buried in code**, inline inside agents and the conversation module.
- **Documents are scattered.** 11 documents, 2 PDFs, 3 `.skill` packages and 3 test scripts at the repo root; 57 files in `docs/` (48 in `archive/`); 15 in `infra/`.
- **Tests live in three places**: `backend/app/tests` (151 files), `backend/tests` (15), repo root (3).

Goal: adopt the owner's standard AI-agent project layout (`config/`, `data/`, `src/{agents, tools, memory, workflows, prompts, evaluation, app}`, `scripts/`, `docs/`), with documents in stage-wise folders. The structure is also shaped for three planned changes (section 5): any API-based model, a LangGraph agent runtime, and a redesigned frontend.

Status: approved by the owner on 2026-10-05. Done so far: stage 0a (start script), stage 0 test baseline, stage 1 (documents), stage 2 (top-level move, with the `run_tasks` key fix), each on its own branch (`stage-0a-start-script`, `stage-1-docs-cleanup`, `stage-2-top-level-move`). Stage 3 (model gateway, branch `stage-3-model-gateway`) is done, with one difference from the plan below: callers keep the `claude_generate*` function names and only the model call moved into `src/llm/`; see `docs/04-development/model-providers.md`. The folder-sorting half of stage 6 is also done (branch `stage-6a-template-folders`): every module is in its template folder, mapped in `module-map.md`. The agent file is split into one file per agent (branch `stage-6c-agent-files`). Still open from stage 6: splitting the other oversized files, extracting prompts, settings into `config/*.yaml`, `workspace/` to `data/`. Stage 4 has its first increment (branch `stage-4-langgraph-run-graph`): the run function is split into four phases and a LangGraph graph with checkpoints can drive them (`RUN_ORCHESTRATOR=langgraph`); what remains is listed in `docs/03-design/langgraph-run-graph.md`. Stage 5 is done as far as one machine allows (branch `stage-5-scale-out`): PostgreSQL, Redis queue, separate workers and PostgreSQL checkpoints were run together and three defects were fixed; see `docs/06-deployment-operations/scale-out.md` for what is verified and what is not. The import rules from stage 6 are in CI (branch `stage-6b-import-rules`, `docs/04-development/layering.md`). Stage 8 has its first increment (branch `stage-8-frontend-journey`): a six-step guided view at `/v2/projects/<id>` beside the classic page; see `docs/03-design/guided-journey-view.md` for what it does and does not do yet. Stage 7 has its first increment (branch `stage-7-conversation-graph`): the message handler is split into four turn phases, a LangGraph graph can drive them (`CONVERSATION_ORCHESTRATOR=langgraph`), and chat messages are answered in the background so the browser no longer times out; see `docs/03-design/conversation-graph.md`. The "from" paths below describe the layout before stage 2. Stage 10 (branch `stage-10-langgraph-native`, 2026-10-06): LangGraph is the only orchestrator (the legacy run and turn drivers and their settings are removed); the run graph has six phases with context assembly and memory writing as their own nodes; the Leading Practice library is searched by a LangGraph retrieval graph (`docs/03-design/leading-practice-rag.md`); a prompt registry holds the first four prompts (`docs/03-design/memory-context-prompts.md`); traces, metrics and logs go to OpenObserve (`docs/06-deployment-operations/observability.md`).

## 0. First deliverable: `scripts/run_agent.sh` with prechecks

One file that checks the environment and packages, then runs backend and frontend together. Built before any restructuring, because every local failure so far (bridge not running, wrong `anthropic` version, broken `claude` command, missing settings) was a setup problem it would have caught.

- `scripts/run_agent.sh` (macOS / Linux). `make dev` and `make doctor` call it. A Windows `run_agent.bat` is a follow-up if needed.
- `./scripts/run_agent.sh` runs prechecks, starts everything, stays in the foreground; `Ctrl+C` stops all of it. `--check` runs prechecks only. `--fix` also repairs what it safely can.
- The Claude CLI bridge moves into the repo (`scripts/claude_cli_bridge.py`) so a clone on another laptop has it. `.run/` (logs, process ids) is added to `.gitignore`.

| Group | Precheck (prints PASS / WARN / FAIL with the fix command) | `--fix` |
|---|---|---|
| Tools | `python3.11` 3.11+, `node` 18+, `npm`, `git` | |
| Environment file | `.env` exists; `JWT_SECRET` 16+ chars and not the placeholder | copies `.env.example`, generates a secret |
| Environment file | `AUTH_ALLOW_SELF_SIGNUP=true` when the database has no users | |
| Model access | A real API key, or bridge mode (`ANTHROPIC_BASE_URL` → `127.0.0.1:8787`) | |
| Model access (bridge) | `claude` command exists and answers a test prompt | |
| Model access (bridge) | `RUN_STUCK_TIMEOUT_SEC` ≥ 1800 and `ANTHROPIC_MAX_TOKENS_PER_RUN=0` | appends them |
| Python packages | venv exists; key imports work (fastapi, sqlalchemy, anthropic, python-pptx, python-docx, openpyxl, sentence-transformers, faiss); `anthropic` below 1.0 | creates venv, installs, pins `anthropic<1` |
| Frontend packages | `frontend/node_modules` present and not older than the lock file | `npm install` |
| Database | database opens; `run_tasks` workaround trigger present (until the code fix lands) | adds trigger |
| Ports | 8787, 8000, 3000 free, or already serving this app's health check | |
| Optional tools | LibreOffice, Redis, Tesseract | warnings only |

Start-up order: bridge (if bridge mode) → backend (wait for `/health`) → frontend (wait for port 3000). Output is prefixed `[bridge]`, `[backend]`, `[frontend]` and also written to `.run/*.log`. If any process exits, the others are stopped.

## 1. Repository layout

The owner's template, with this app's parts mapped in. Additions to the template are marked `(+)` and explained below the tree.

```
Advise-Workbench/
├── config/
│   ├── agent_config.yaml         orchestrator choice, agents enabled, tool rounds, repair loops, feature flags (swarm, bash tool, MCP)
│   ├── model_config.yaml         provider, model per tier (default / planning / critique), token budgets, timeouts, capability flags
│   ├── logging_config.yaml       log levels, tracing (Langfuse / OpenTelemetry), metrics
│   ├── skills/                   (+) the 15 skill folders, skill_registry.json, output_types.json
│   ├── quality/                  (+) quality contracts and rules
│   ├── branding/                 (+) brand definitions and templates
│   └── mcp_servers.json          (+)
├── data/                         runtime data, not in git except examples/
│   ├── raw/                      uploaded source documents, per project
│   ├── processed/                parsed text and chunks, per project
│   ├── vector_db/                embeddings and search indexes (documents, wiki, leading practices)
│   ├── outputs/                  (+) run folders: generated files, QA and guardrail reports
│   ├── wiki/                     (+) project wikis and the shared leading-practice wiki
│   └── examples/                 Northwind sample documents and run scenarios (from infra/test-artifacts)
├── src/
│   ├── agents/
│   ├── tools/
│   ├── memory/
│   ├── workflows/
│   ├── prompts/
│   ├── evaluation/
│   ├── app/
│   ├── core/                     (+)
│   ├── llm/                      (+)
│   ├── deliverables/             (+)
│   ├── guardrails/               (+)
│   └── extensions/               (+)
├── frontend/                     (+) Next.js web app (the template's `ui.py` is a full application here)
├── tests/                        (+) one test tree: unit/, integration/, golden/, security/
├── migrations/                   (+) Alembic database migrations
├── scripts/
│   ├── run_agent.sh              start script with prechecks (section 0)
│   ├── build_index.py            build or refresh document, wiki and leading-practice indexes
│   ├── evaluate.py               run the baseline scenarios and compare scores
│   └── claude_cli_bridge.py      (+) local bridge for running on a Claude subscription
├── docs/
│   ├── README.md                 index of all documents
│   ├── SETUP.md                  install and run
│   └── 00-overview/ … 99-archive/   stage-wise folders (section 2)
├── requirements.txt              pinned versions (generated lock; fixes the anthropic 1.x breakage)
├── pyproject.toml                (+) tool settings: pytest, ruff, import rules
├── docker-compose.yml
├── Dockerfile                    backend image; `frontend/Dockerfile` for the web app
├── Makefile, .env.example, README.md, CLAUDE.md
└── .gitignore
```

Why the template needs these additions:

| Addition | Reason |
|---|---|
| `src/core/` | Settings loader, database, authentication, security helpers and observability are shared by everything and belong to no single template folder |
| `src/llm/` | One place for model providers, so the app can run on any API-based model (5A) |
| `src/deliverables/` | About 10,000 lines of DOCX / PPTX / XLSX / PDF / draw.io builders that contain no agent logic |
| `src/guardrails/` | Permission pipeline, seven gates, hooks and data protection are run-time controls, different from offline evaluation |
| `src/extensions/` | Optional features (financial models, swarm, scheduler) kept out of the core so the main app stays light |
| `frontend/`, `tests/`, `migrations/` | The web app, the single test tree and database migrations |

The `backend/` folder disappears: its Python code becomes `src/`, its `config/` becomes the root `config/`, and `backend/workspace/` becomes `data/`.

Leaves the root: the 9 extra documents and 2 PDFs (to `docs/`), 3 `.skill` packages (to `config/skills/_packages/`), 3 `test_*.py` scripts (to `tests/`), `infra/` (split into `docs/`, `scripts/`, `data/examples/`), `.claire/` (deleted).

## 2. Documentation: `docs/` by stage

```
docs/
├── README.md                     index (replaces DOCUMENTATION_INDEX.md)
├── SETUP.md                      prerequisites, install, run, troubleshooting
├── 00-overview/                  product brief, EXECUTIVE_BRIEF, COMPETITIVE_ANALYSIS (+ dashboard), solution overview PDF, glossary
├── 01-requirements/              BRDs (platform, frontend), gap analyses, capability bug notes
├── 02-architecture/              ARCHITECTURE.md, target structure (this plan), run lifecycle, data model, wiki architecture
│   └── adr/                      decision records (PPTX canvas renderer spike, LangGraph decision)
├── 03-design/                    module designs: token budget, PPTX renderer, coordinator refactor, database transactions, financial modules, swarm
├── 04-development/               coding standards, how to add a skill / tool / agent / output type, frontend integration guide
├── 05-testing/                   test strategy, TEST_REPORT, CODE_QUALITY_EVAL, test scenarios, sample engagement outputs
├── 06-deployment-operations/     OPERATIONS, PRODUCTION_TOPOLOGY, SECURITY, hardening and concurrency plans, bash / text-editor tool security
├── 07-user-guide/                using the app: projects, Sheldon, runs, wiki, leading-practice library
├── 08-project-management/        roadmap, task plan (repo guide workbook), phase summaries, status reports
└── 99-archive/                   the 48 historical files, unchanged
```

Skill documents (`config/skills/*/SKILL.md` and companions) stay with their skills.

## 3. `src/` in detail

File names follow the template where the app has an equivalent; current source files are shown in brackets.

```
src/
├── agents/
│   ├── base_agent.py             shared agent contract: context in, output out, validation [agent_types.py, prompt_hygiene.py]
│   ├── planner_agent.py          builds the execution plan [coordinator_planning.py]
│   ├── supervisor_agent.py       dispatches specialists, collects results, triggers repair [coordinator.py, coordinator_execution.py, coordinator_state_manager.py]
│   ├── tool_agent.py             generic agent that works through tools in rounds [run_subagent_tool_loop]
│   ├── conversation_agent.py     Sheldon: discovery, storyline, plan proposal [api/projects/conversation.py logic, slide_negotiator, storyline_builder, agent_personality]
│   ├── specialists/              one file per document agent: raci, sop, narrative, process_map, xlsx, pdf, docx, pptx/ [subagents.py split]
│   └── repair/                   critique-and-repair for PPTX and DOCX
├── tools/
│   ├── registry.py               tool list, schemas, per-skill and per-output defaults [tool_registry.py]
│   ├── web_search.py             Tavily / Brave / Google; web_capture
│   ├── code_executor.py          sandboxed bash and text-editor execution [bash_executor.py, text_editor_executor.py]
│   ├── api_tool.py               external tools over MCP [services/mcp/]
│   ├── retrieval_tool.py, memory_tool.py, builder_tools.py, validator_tools.py, draft_tools.py
│   └── custom_tool.py            template and base for project-specific tools
├── memory/
│   ├── short_term.py             conversation state, digest, compaction for the current run [conversation_state, conversation_digest, context_compaction]
│   ├── long_term.py              memory items, project profile, consent rules [memory_context, memory_consent, memory_event_service]
│   ├── memory_store.py           storage and search: database rows, embeddings, BM25 [retrieval.py]
│   └── knowledge/                project wiki and leading-practice library [wiki_*.py, leading_practices.py]
├── workflows/
│   ├── agent_graph.py            LangGraph run graph (5B); until then a thin wrapper over the supervisor
│   ├── orchestrator.py           run lifecycle: admission, execute, evaluate, finalize; queue and events [run_worker.py split, run_queue/, run_events, run_tasks]
│   ├── task_router.py            routes a request to conversation, plan or run, and to output types [conversation_router, output_format_detection, _intent.py]
│   ├── conversation_graph.py     Sheldon's flow as a graph (5B)
│   └── nodes/, checkpoint.py, events.py     graph steps, resume storage, translation to the UI's event format
├── prompts/
│   ├── system_prompts.py         system prompts for planner, specialists, critics, guardrail judges, Sheldon (extracted from inline strings)
│   ├── templates.py              reusable prompt builders
│   └── skill_loader.py           reads skill cards from config/skills [skill_document.py]
├── evaluation/
│   ├── eval_agents.py            QA loop, evaluators, visual QA, design review, evidence check [qa.py, evaluators.py, visual_qa.py, evidence_*]
│   ├── metrics.py                quality framework, scores, thresholds, format QA [quality_framework.py, docx_qa, pptx_qa, xlsx_qa]
│   └── test_cases.py             baseline scenarios A to F and expected minimum scores
├── app/
│   ├── main.py                   application start and router registration only
│   ├── api/                      HTTP routes by area: auth, projects, documents, conversation, runs, memory, wiki, skills, admin [api/*.py; runs.py and conversation.py split]
│   └── schemas/                  request and response models
│   (the template's ui.py is the Next.js app in /frontend)
├── core/                         (+) config loader (reads config/*.yaml and .env), db/ (models per domain, session), auth, security/, observability/, storage
├── llm/                          (+) gateway.py, providers/ (anthropic_api, claude_cli, openai_compatible), capabilities.py, budget.py, pricing.py, retry.py
├── deliverables/                 (+) docx/, pptx/, xlsx/, pdf/, process_map/, figures/, export.py
├── guardrails/                   (+) permission_pipeline.py, gates.py, hooks.py, policy.py, data_protection/
└── extensions/                   (+) financial_models/, swarm/, scheduler/ : optional, loaded only by app/main.py
```

**Dependency rule (enforced in CI with `import-linter`):**
`core` ← `llm` ← `prompts / tools / deliverables / memory` ← `evaluation / guardrails` ← `agents` ← `workflows` ← `app`. Nothing imports upward; `extensions` are imported only by `app/main.py`.

**Size rule:** target under 500 lines per file.

**Import root:** code is imported as `src.agents…`, `src.tools…` (run with `uvicorn src.app.main:app` from the repo root). This avoids clashes between generic folder names such as `agents` or `tools` and installed packages.

## 4. Frontend: folders that follow the user's journey

```
frontend/
├── app/                          routes only: each page.tsx imports from features/
├── features/
│   ├── auth/  projects/
│   ├── journey/                  brief/ (Sheldon), sources/, plan/, build/, review/, deliver/
│   ├── library/                  leading practices, skills
│   ├── models/  memory/  settings/  admin/
│   └── <feature>/ = components/, hooks/, api.ts, types.ts, tests
├── components/ui/                design-system primitives, shell, toast
├── lib/, stores/, tests/, e2e/
└── Dockerfile
```

Files to split first: `hooks/useRunStudio.tsx` (1,348 lines), `ToolActivityFeed.tsx` (1,109), `ZoneAInstruction.tsx` (929), `app/memory/page.tsx` (735).

## 5. Future direction the structure is built for

### 5A. Run on any API-based model
- **Today:** the Anthropic client is constructed directly in 6 places (`services/claude.py`, `services/claude_tools.py`); about 60 call sites use three functions.
- **Target:** every caller uses `src/llm/gateway.py`. `config/model_config.yaml` picks the provider (`anthropic`, `claude_cli`, `openai_compatible` for OpenAI, Groq, Azure, local) and the model per tier.
- **Capability flags** handle differences: no extended thinking → plain planning call; no vision → visual QA skipped with a clear note; no tool calling → single-shot generation.
- **Cost:** prompts and skills are tuned for Claude; each new provider needs a baseline run (`scripts/evaluate.py`) before users get it.

### 5B. Convert the agent runtime to LangGraph
- **Today:** custom coordinator plus a 2,020-line run worker; approvals as status flags; resume by replaying the event log.
- **Target:** `workflows/agent_graph.py`: context → extract → plan → *approve (interrupt)* → generate (parallel per deliverable) → compose → QA and repair loop → guardrails → *review (interrupt)* → finalize. `workflows/conversation_graph.py` for Sheldon.
- **Kept and called from graph nodes:** specialists, deliverable builders, evaluation, guardrails, tools (wrapped as LangChain tools).
- **Checkpointing** with the LangGraph SQLite / Postgres saver: a restarted run continues from the last finished step; replaces the pause / resume flags and the stuck-run watchdog.
- **Frontend contract preserved:** `workflows/events.py` emits the existing `run-events-v1` events.
- **Switch, not a rewrite in place:** `orchestrator: legacy | langgraph` in `config/agent_config.yaml`; both run on the baseline scenarios until the graph matches, then the legacy supervisor loop is removed.
- **Order:** 5A first, then the run graph, then the conversation graph. New packages: `langgraph`, `langgraph-checkpoint-sqlite` / `-postgres`, `langchain-core`, provider packages.

### 5C. Frontend redesign: guided journey, clearer navigation, more control
Problems seen in use: no sense of which step you are in; a run starts from a chat message with no plan screen; asking for DOCX produced PPTX; long calls show "fetch aborted"; failures are only visible in logs.
- **Navigation:** fixed left menu (Projects, Library, Admin); inside a project an always-visible six-step bar: **Brief → Sources → Plan → Build → Review → Deliver**.
- **Storyline:** one purpose and one primary action per step; Sheldon available as a side panel in every step.
- **Control:** explicit choice of deliverables and formats and an editable outline in Plan; per-stage progress with pause / resume / stop in Build; preview, evidence accept / reject, findings in plain words and re-run from a stage in Review; errors shown with reason and next action.
- **Responsiveness:** streamed chat replies and background jobs with progress.
- **Method:** UX audit and information architecture → wireframes → design system → build under `/v2` until complete.

### 5D. Scale to more users and runs
LangGraph and LangChain do not add capacity by themselves; these do. Most already exist in the code as options that are switched off.
- **Queue and workers:** `RUN_QUEUE_BACKEND=redis` with separate worker processes (`app/workers/run_execution_worker.py`) instead of the in-process queue; API servers stay stateless.
- **Database:** PostgreSQL instead of SQLite (migrations already run against Postgres in CI).
- **Run state:** LangGraph's Postgres checkpointer, so any worker can continue any run and restarts lose nothing.
- **Provider limits:** per-provider rate limiting and retry in `src/llm/`, and spreading load across providers once 5A is in.
- **Proof:** the load scripts already in `infra/load/` (`rest_burst.py`, `soak_500_runs.py`, `slo_gate.py`, `sse_stream_smoke.py`) run against a shared environment.

## 6. How the work is staged

Owner decisions (2026-10-05): **bring LangGraph forward**, and plan for all three kinds of scaling: other model providers, more users and runs, and team growth. So the gateway and the run graph come straight after the top-level move, and the detailed clean-up of the remaining code follows them.

All work on branches. Behaviour must not change in stages 0a to 2.

| Stage | Scope | Risk |
|---|---|---|
| 0a | `scripts/run_agent.sh` with prechecks; bridge into `scripts/`; `make dev` / `make doctor` | Low |
| 0 | Save this structure as `docs/02-architecture/target-structure.md`; run all tests once and run scenarios A to F for a quality baseline (`scripts/evaluate.py`); add a "Target Structure" sheet and tasks to the repo guide workbook | None |
| 1 | Documents and root clean-up: `docs/` stage folders, `README.md` and `SETUP.md`, sample data to `data/examples/`, helper scripts to `scripts/` | Low |
| 2 | Top-level move: `backend/app` → `src/`, `backend/config` → `config/`, Alembic → `migrations/`, tests → `tests/`; pinned `requirements.txt`; CI, Docker, Makefile. Imports change from `app.…` to `src.…` in one mechanical pass. Blocking fixes go in here: per-run key for `run_tasks`, self-signup default | Medium |
| 3 | **Model gateway (5A):** `src/llm/` with providers for Anthropic API, Claude CLI and OpenAI-compatible; `config/model_config.yaml`; all 60 call sites switched to the gateway | Medium |
| 4 | **LangGraph run graph (5B):** `src/workflows/agent_graph.py`, nodes, checkpointing, event translation, `orchestrator: legacy \| langgraph` switch. The pieces the graph calls are moved into their template folders as part of this stage (`agents/specialists/` split out of `subagents.py`, `tools/`, `prompts/`, `evaluation/`, `guardrails/`). The legacy orchestrator is frozen, not edited | High |
| 5 | **Scale-out (5D):** Redis queue and worker processes, PostgreSQL, Postgres checkpointer, shared team environment, load tests | Medium |
| 6 | Finish the clean-up: remaining code sorted into the template folders (`core`, `memory`, `deliverables`, `app/api`, `extensions`), oversized files split, settings into `config/*.yaml`, `workspace/` → `data/`, `import-linter`; remove the legacy orchestrator once the graph matches the baseline | Medium |
| 7 | **LangGraph conversation graph (5B)** for Sheldon, with streamed replies | High |
| 8 | **Frontend (5C):** feature folders, then the six-step journey redesign under `/v2` | High |

**Who does what:** AI engineers on stages 3, 4 and 7; full-stack developer on 0a, 1, 2, 5 and 8; stage 6 shared. Stage 8 can start as soon as stage 2 is merged.

**Risk of bringing LangGraph forward, and how it is contained:** the graph is built while part of the code is still in the old flat layout. To keep the two changes from colliding: stage 2 must be merged and green before stage 4 starts; stage 4 only moves the files the graph calls; the legacy orchestrator stays untouched as the fallback behind the switch; the stage-0 baseline decides when the graph is good enough to become the default.

## Critical files

- Moves: everything under `backend/`, `frontend/`, `docs/`, `infra/` and the repo root.
- Path references to update: `.github/workflows/ci.yml`, `Makefile`, `README.md`, `CLAUDE.md`, `pyproject.toml` (pytest paths, ruff ignores), `alembic.ini` and `env.py`, `Dockerfile*`, `docker-compose.yml`, `frontend/next.config.js`.
- Storage paths: `app/services/storage.py` (`workspace_path`, `ensure_workspace`) and the modules that build workspace paths themselves (wiki, runs).
- Settings: `app/core/config.py` (629 lines, about 218 settings) becomes a loader over `config/*.yaml` plus `.env`.
- Reused as-is: router aggregation pattern in `app/api/projects/_router.py`, `app/api/wiki/_router.py`, `app/api/models/_router.py`; skill and quality files in `config/`.

## Verification

After every stage:
1. Backend tests match the stage-0 baseline (`pytest tests -q`).
2. `ruff check src` passes; from stage 5, `lint-imports` passes.
3. `cd frontend && npm run lint && npm run test:vitest && npm run build`.
4. Endpoint count unchanged: 242 HTTP operations + 3 WebSockets from the app's OpenAPI schema.
5. `./scripts/run_agent.sh --check` passes; `./scripts/run_agent.sh` starts everything; Scenario C on the Northwind samples produces a deck.
6. The repo guide workbook rebuilds with the new paths.

Stage-specific checks:
- **Stage 3 (gateway):** Scenario C completes with each supported provider; a provider without vision or tool calling degrades with a clear message.
- **Stages 4 and 7 (LangGraph):** with the LangGraph orchestrator, baseline scores are at or above the legacy ones; killing the backend mid-run and restarting resumes from the last completed step; the UI shows the same event timeline.
- **Stage 5 (scale-out):** two API processes and two workers on Redis and PostgreSQL pass `infra/load/slo_gate.py`; a run started on one worker finishes after that worker is stopped.
- **Stage 8 (frontend):** a first-time user completes Brief to Deliver without the terminal; choosing DOCX produces a DOCX; a failed run shows its reason and next action on screen.

## Open points for the owner to revise

- The five additions to the template under `src/` (`core`, `llm`, `deliverables`, `guardrails`, `extensions`): keep as separate folders, or fold some into template folders.
- `data/` layout: per-kind folders with a project subfolder (as drawn), or one folder per project.
- Whether settings should move to `config/*.yaml` now (stage 4) or stay in `.env` until the model gateway (stage 6).
- Which model providers to support first after Anthropic (each needs its own baseline run).
- Whether the six step names (Brief, Sources, Plan, Build, Review, Deliver) fit how your teams talk about the work.
- The existing 8-week task plan (new skills such as the risk and control matrix and KPI dictionary) competes with stages 3 to 8 for the same three people. Stages 0a to 5 are roughly two months on their own, so the new-skills work would move after them unless you choose otherwise.
- Where the shared environment for stage 5 will run (a cloud account or an internal server).
- Start script for macOS / Linux only, or also Windows.
