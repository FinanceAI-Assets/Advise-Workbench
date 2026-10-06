# Running on more than one process

How to run the app for many users: PostgreSQL in place of SQLite, a Redis queue in place of the in-process one, and separate worker processes. All of this already existed in the code as options; this page records the settings, what was tested, and what was found.

## Layout

```
browser -> web app (Next.js) -> API processes (uvicorn --workers N)   stateless
                                     |            |
                                PostgreSQL      Redis  <- run queue, cache, heartbeats
                                     |            |
                               worker processes (one or more)        execute runs
```

- **API processes** accept requests and put approved runs on the Redis queue. They do not execute runs.
- **Worker processes** take runs from the queue and execute them.
- **PostgreSQL** holds all application data and, with the LangGraph orchestrator, the run checkpoints.
- **The workspace folder** (uploads, run outputs, wikis) must be a path every API and worker process can read and write, for example a shared volume.

## Settings

| Setting | Value | Why |
|---|---|---|
| `DATABASE_URL` | `postgresql+psycopg://user:password@host:5432/dbname` | SQLite allows one writer and cannot be shared |
| `REDIS_URL` | `redis://host:6379/0` | Queue, cache and worker heartbeats |
| `RUN_QUEUE_BACKEND` | `redis` | Runs go to Redis instead of an in-process queue |
| `CACHE_ALLOW_MEMORY_FALLBACK` | `false` | Start-up fails if Redis is unreachable, instead of each process quietly using its own cache |
| `RUN_CHECKPOINT_STORE` | `postgres` | Checkpoints live in the shared database, not in a file on one machine |
| `WORKSPACE_ROOT` | a shared path | Same files for every process |
| `ADVISE_WORKBENCH_ENV` | `staging` or `production` | Switches off development-only leniencies |

## Commands

```bash
alembic upgrade head                                            # once per deployment
uvicorn src.app.main:app --host 0.0.0.0 --port 8000 --workers 2 # API
python -m src.workflows.workers.run_execution_worker            # one per worker process
```

Checks:

| Address | Shows |
|---|---|
| `/health/ready` | Database and Redis reachable, queue backend |
| `/workers/health` | Worker processes that sent a heartbeat recently |
| `/metrics/prometheus` | Counters and latencies |

## What was tested (2026-10-06)

On one machine, with PostgreSQL 16 and Redis 8 started temporarily on non-default ports:

| Test | Result |
|---|---|
| All 20 migrations on an empty PostgreSQL database | Pass, including the `run_tasks` key change |
| Two API processes and two workers starting at the same moment on an empty database | Pass after the fix below; both workers report healthy |
| 2,000 requests to `/health` at 200 concurrent (`scripts/load/rest_burst.py`) | 0 errors, about 3,170 requests per second, p95 88 ms |
| Sign-in and project creation through the API on PostgreSQL | Pass after the fix below |
| LangGraph checkpoints in PostgreSQL: run, simulated crash, resume, 8 runs in parallel | Pass |
| A run placed on the Redis queue | Picked up by a separate worker and executed through the graph; checkpoints written to PostgreSQL |

## Problems found and fixed

| Problem | Effect | Fix |
|---|---|---|
| Processes starting together raced to create missing tables | One process crashed at start-up with a duplicate-key error on `pg_type` | `init_db` takes a PostgreSQL advisory lock around table creation (`src/core/db/session.py`) |
| Creating a project inserted the membership row before the project row | Every project creation failed on PostgreSQL with a foreign-key error. SQLite does not enforce foreign keys by default, so it never showed locally | The project is flushed first (`src/app/api/projects/crud.py`) |
| Checkpoint tables were created on the first run | The set-up builds an index concurrently, which waits for every open transaction; a session left idle in a transaction stalled the run | Tables are created at process start (`prepare_checkpoint_store`) |

## Not verified, and known gaps

- **A full run with a real model in this layout.** The test environment had no model access, so the queued run was observed entering generation but not finishing.
- **The run-lifecycle soak script is out of date.** `scripts/load/soak_500_runs.py` creates runs directly, but the API now requires a confirmed plan first and answers `409`. It needs a plan-confirmation step before it can measure anything.
- **Other insert-order problems may exist.** Project creation was the first write on PostgreSQL and it failed; other endpoints that add a parent and a child row in one commit have not been exercised on PostgreSQL. Running the test suite against PostgreSQL would find them.
- **Shared workspace storage** was not tested across machines; everything ran on one disk.
- **Several machines, a load balancer and TLS** are outside what was tested. See `PRODUCTION_TOPOLOGY.md`.
