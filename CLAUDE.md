# Advise Workbench — agent onboarding

Use this file as the front door; everything else is detail in-tree.

## Read first

- **`README.md`** — runbooks, Cowork-style architecture summary, and where features live.
- **`docs/02-architecture/ARCHITECTURE.md`** — layered design, data flow, and integration points.
- **`docs/README.md`** — index of all documents, grouped by stage (`docs/00-overview` … `docs/99-archive`).
- **`README_RUN.md`** — the services, prerequisites, how to start, and one example from sample input to output files.
- **`docs/SETUP.md`** — install, configure and run; `./scripts/run_agent.sh` checks the environment and starts everything.
- **`docs/02-architecture/target-structure.md`** — the approved restructuring plan and its stages.

## Local configuration

Application settings load from the repo-root **`.env`** (one file; there is no separate backend `.env`). Code lives in **`src/`** and is imported as `src.…`; run commands from the repo root (`uvicorn src.app.main:app`, `pytest tests/unit`, `alembic upgrade head`). **`JWT_SECRET`** must be a strong value (≥16 characters, not a placeholder); validation is in `src/core/config.py`. After a fresh clone, generate and append one:

```bash
make dev.secret
```

The **`pytest`** suite under `tests/integration/` sets `JWT_SECRET` via `tests/integration/conftest.py` so CI and local test runs do not need a real `.env`.

## Code map (high signal)

| Area | Location |
|------|----------|
| FastAPI app & middleware | `src/app/main.py` |
| Auth helpers | `src/core/auth.py` |
| Wiki HTTP API | `src/app/api/wiki.py` (all routes require auth; project wikis enforce `require_project_role`) |
| Wiki ingest / refresh | `src/memory/knowledge/wiki_ingest.py`, `wiki_refresh.py` |
| SSRF-safe HTTP GET | `src/core/security/http_fetch.py` (`safe_get`) |
| Office zip safety | `src/core/security/zip_safety.py` |
| Deliverables | `src/deliverables/` |
| Frontend wiki UI | `frontend/components/wiki/` |

## Repository hygiene

Treat **`advise_workbench.db`**, the entire **`workspace/`** tree, Office lock files (`~$*`), and stray generated **`.pptx` / `.docx`** at the repo root as machine-local. They are ignored from git via the root **`.gitignore`**. Historical status write-ups live under **`docs/99-archive/`**; keep the root clean (README, README_RUN, this file, Makefile, Docker and env files); every other document belongs under `docs/`.

## Remediation roadmap

Cross-cutting work (security hardening, PPTX/XLSX/DOCX quality, observability, module splits) is tracked as a **phased program** (Phase 0 hygiene → Phase 1 security criticals → parallel doc-quality and DX tracks). When implementing, align with existing utilities: `get_current_user` / `require_project_role`, `BrandingContext` / `branding_service`, `otel_tracing` / `langfuse_tracing`, `run_budget` / `token_budgets`, and `zip_safety` for any new zip paths.
