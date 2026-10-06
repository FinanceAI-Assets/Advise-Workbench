# Setup

How to install and run Advise Workbench on a Mac or Linux machine.

## 1. Prerequisites

| Tool | Version | Install (macOS) |
|---|---|---|
| Python | 3.11 or newer | `brew install python@3.11` |
| Node.js and npm | 18 or newer | `brew install node` |
| git | any | `xcode-select --install` |

Access to a language model, in one of three ways (details in [04-development/model-providers.md](04-development/model-providers.md)):

- **Anthropic API key** (default). A workspace-scoped key (`sk-ant-api03-...`).
- **Claude Code subscription.** The Claude Code CLI, signed in: `npm install -g @anthropic-ai/claude-code`, then run `claude` once. No API key. For personal use on your own machine; agents cannot call tools while generating.
- **An OpenAI-style service.** OpenAI, Groq, an Azure-style gateway or a local server.

## 2. Configure

```bash
cp .env.example .env
```

Edit `.env`:

| Setting | Value |
|---|---|
| `JWT_SECRET` | Any random string of 16+ characters. `./scripts/run_agent.sh --fix` generates one |
| `AUTH_ALLOW_SELF_SIGNUP` | `true` (already set in `.env.example`), so the first sign-in can create your user. Use `false` on shared deployments |
| Anthropic API | `ANTHROPIC_API_KEY=<your key>` |
| Claude Code subscription | `LLM_PROVIDER=claude_cli` |
| OpenAI-style service | `LLM_PROVIDER=openai_compatible`, `LLM_MODEL=<model>`, `LLM_API_KEY=<key>`, and `LLM_BASE_URL=<address>` unless it is OpenAI itself |
| Claude Code via the bridge (older setup, still works) | `ANTHROPIC_BASE_URL=http://127.0.0.1:8787` and `ANTHROPIC_API_KEY=not-used-cli-bridge` (a placeholder; the app requires the field to be non-empty) |
| Either Claude Code setup, recommended | `RUN_STUCK_TIMEOUT_SEC=1800` and `ANTHROPIC_MAX_TOKENS_PER_RUN=0`. `--fix` adds both |

## 3. Check and install

```bash
./scripts/run_agent.sh --check --fix
```

This checks tools, settings, model access, Python and frontend packages, the database and ports. With `--fix` it creates `.venv` at the repo root, installs the pinned packages from `requirements-dev.txt`, and repairs what it safely can. Every line is `PASS`, `WARN`, `FIXED` or `FAIL`; a `FAIL` shows the command that fixes it.

## 4. Run

```bash
./scripts/run_agent.sh        # or: make dev
```

It starts the bridge (in bridge mode), the backend and the frontend, and stops all of them on `Ctrl+C`. Logs are written to `.run/`.

For monitoring (traces, metrics and logs in OpenObserve), run `./scripts/openobserve.sh setup` once; `run_agent.sh` then starts OpenObserve as well. See `docs/06-deployment-operations/observability.md`.

| Service | Address |
|---|---|
| Web app | http://localhost:3000 |
| Backend health | http://127.0.0.1:8000/health |
| API reference | http://127.0.0.1:8000/docs |
| Bridge (bridge mode) | http://127.0.0.1:8787 |

Sign in with any email and password; the first sign-in creates the account.

## 5. First test

Sample documents for a fictional client are in `data/examples/northwind-p2p/`. Upload files `01`, `02` and `05` from `source-documents/`, then paste a scenario from `run-scenarios/README.md` into the chat. See [07-user-guide/using-the-app.md](07-user-guide/using-the-app.md).

## 6. Optional tools

| Tool | What it enables | Install (macOS) |
|---|---|---|
| LibreOffice | Proper rendering of decks and documents for visual quality checks | `brew install --cask libreoffice` |
| Redis | Shared cache and a multi-process run queue | `brew install redis && brew services start redis` |
| Tesseract and Poppler | Reading scanned PDFs | `brew install tesseract poppler`, then `.venv/bin/pip install pdf2image pytesseract` |
| PostgreSQL | Production database in place of SQLite | set `DATABASE_URL`, then `make db.migrate` |

## 7. Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Sign-in says "Invalid credentials" on a new install | Self-signup is off by default | `AUTH_ALLOW_SELF_SIGNUP=true` in `.env`, restart |
| `unexpected keyword argument 'temperature'` | `anthropic` 1.x is installed | `.venv/bin/pip install -r requirements.txt` (pins `anthropic` below 1.0) |
| "Connection error", then "Claude circuit breaker is open" | Bridge not running | Start with `./scripts/run_agent.sh`; the breaker clears after 60 seconds or a backend restart |
| `claude: command not found` after it worked before | The CLI's auto-update left a broken install | `npm install -g @anthropic-ai/claude-code` |
| "fetch aborted" in the chat | Before 2026-10-06 only: chat messages, plan decisions and outline changes are now answered in the background and the page polls for the reply | Update to the latest branch. The reply was saved; refresh the page |
| Sign-in fails, or the chat says "database is locked", while a run is going | Before 2026-10-06 only: a run held the database write lock for the whole generation | Update to the latest branch; wait for the run to finish meanwhile |
| "Run created but couldn't be queued" after saying "go" | Before 2026-10-06 only: the run was queued before it was saved | Update to the latest branch; start the run again from the plan |
| A run produces a generic deck and fails the evidence check | No model call succeeded during the run | Check the bridge is running and answering |
| `UNIQUE constraint failed: run_tasks.id` on a second run | An old database from before the checklist key fix | Restart the backend; it rebuilds the table on start-up and keeps the rows |
| "Claude gate evaluation failed" during checks | The default cap of 50,000 tokens per run is used up | `ANTHROPIC_MAX_TOKENS_PER_RUN=0` |
| Run stops with "Execution timed out after 600s" | Slow generation through the CLI | `RUN_STUCK_TIMEOUT_SEC=1800` |
| Redis "connection refused" messages at start-up | Redis is not installed | Harmless on one machine |

## 8. Tests

```bash
pytest tests/unit -q && pytest tests/integration -q     # or: make test
cd frontend && npm run lint && npm run test:vitest && npm run build
```

Run the backend tests in a clean checkout or without a `.env` that points at a local bridge: `src/app/main.py` loads `.env` over the test settings, and some tests then wait on a bridge that is not running.
