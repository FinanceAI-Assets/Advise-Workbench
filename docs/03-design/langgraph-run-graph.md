# Run execution with LangGraph

How a run is executed, what the LangGraph orchestrator adds, and what is still to do.

## Summary

A run attempt has six phases, driven by a LangGraph graph with one node per phase and a checkpoint after each. If the server restarts mid-run, the run continues from the last finished phase.

LangGraph is the only orchestrator. The earlier `legacy` driver (one function calling the phases in a row) and the `RUN_ORCHESTRATOR` setting were removed on 2026-10-06.

## The six phases

All six are in `src/workflows/orchestrator.py`.

| Phase | Function | What it does | Ends the attempt when |
|---|---|---|---|
| prepare | `_phase_prepare` | Loads the run, honours abort flags, runs the permission pipeline, marks the run as running | The run is missing, aborted, denied, or already finished |
| context | `_phase_context` | Assembles what the coordinator starts from: run settings, the plan, the conversation digest (short-term memory, compacted to a character budget) | Never |
| generate | `_phase_generate` | Pre-execution hooks, the coordinator (planning and document agents), saves artifacts, final artifact QA, streams output chunks | A hook aborts, the run is aborted or times out, the token budget runs out, or an expected output is missing |
| evaluate | `_phase_evaluate` | Visual QA, guardrail report, evidence gate, evaluator pipeline | A check fails: the run is re-queued for remediation (up to 3 times) or marked failed |
| remember | `_phase_remember` | Writes long-term memory: the artifact summary event, the project memory profile, the user's learning count | Never |
| finalize | `_phase_finalize` | Marks the run ready for review, writes events, post-execution hooks | Always (it is the last phase) |

A phase returns an outcome `(ok, error)` when it ends the attempt, or `None` to continue.

### What the phases share

A `RunJob` carries the run's inputs and a dictionary of working variables. Each phase reads what it needs from the earlier ones and stores its own. `PHASE_CARRY` lists the variables that cross a phase boundary:

| Needed by | Variables |
|---|---|
| generate | `init_state`, `requested`, `output_type_representations`, `hard_gate_enabled`, `plan_payload_obj`, token usage and cost |
| evaluate | `state`, `run_todos`, `requested`, `plan_payload_obj`, `final_artifact_report`, `hard_gate_enabled`, `run_dir`, token usage and cost |
| remember | `state` |
| finalize | `state`, `run_todos`, token usage and cost |

The database session and the `Run` row are not carried: they are opened again when a run resumes.

## The graph

`src/workflows/agent_graph.py`

```
START -> prepare -> context -> generate -> evaluate -> remember -> finalize -> END
            |                      |           |
            +----------------------+-----------+--> END   (a phase returned an outcome)
```

- **One node per phase.** A node calls the phase function, then stores the variables the remaining phases need in the graph state.
- **Checkpoint after every node**, written before the next node starts (`durability="sync"`).
- **One graph thread per attempt.** The thread id is `<run id>:attempt-<n>`, where `n` is the number of remediation rounds so far. Remediation still works as before: the evaluate phase re-queues the run, and the new attempt gets a fresh thread.
- **Errors.** An exception in any phase after prepare is recorded as a failed run by `fail_run_job`.
- **Tracing.** Each node is one span, `run.phase.<name>` (see `docs/06-deployment-operations/observability.md`).
- **Clean-up.** When an attempt reaches its end, its checkpoints are deleted.

### Resume after a restart

1. On start-up, `reconcile_stalled_approved_runs_on_startup` finds runs still marked running.
2. A run whose current attempt has a checkpoint with phases still to run is re-queued, and a `step` event with `status: execution_resumed` is written. A run with no such checkpoint is failed as orphaned.
3. The graph is invoked for the same thread. LangGraph skips the finished nodes.
4. The first remaining node rebuilds the job: it opens a session, runs the prepare phase again to reload the run and re-check admission, then restores the carried variables from the checkpoint.

The practical effect: if the server stops during the checks, the 10 to 20 minute generation is not repeated.

A run that was cancelled while the server was down stops at the admission re-check.

### Checkpoint store

`src/workflows/checkpoint.py`

| Store | Location | Use |
|---|---|---|
| `sqlite` (default) | `workspace/.checkpoints/run_graph.sqlite` | One machine |
| `postgres` | The application database (`DATABASE_URL`) | Several workers; needs the `langgraph-checkpoint-postgres` package. Written but not yet run against a PostgreSQL server |

## How it was verified

- The whole unit and integration suites go through the graph; the existing end-to-end run tests write checkpoints.
- `tests/unit/test_run_graph.py` covers phase order, early stop, error handling, a simulated crash during evaluate followed by a resume that does not repeat generate, and a simulated crash during generate followed by a resume that does not assemble the context again.
- `test_run_started_through_the_api_reaches_an_end_under_the_graph` starts a run through the API with the real phases and requires it to finish. It was added after a defect was found on 2026-10-06 (see below).
- **Live run, 2026-10-06** (Claude CLI bridge, Scenario C deck, `RUN_ORCHESTRATOR=langgraph` and `CONVERSATION_ORCHESTRATOR=langgraph`): the chat turns, generation and checks ran through the graphs; failed checks re-queued the run onto a new graph thread (`attempt-1`, `attempt-2`) and the finished attempt's checkpoints were deleted.
- **Kill and restart, same run:** the backend was killed with `kill -9` right after attempt 2's generation was checkpointed. On restart the run was re-queued with `execution_resumed (restart, langgraph)`, re-checked admission, skipped generation and went straight to the checks.

### Defect found and fixed on 2026-10-06

With `langgraph`, every real run hung. The coordinator state that is carried from generate to the checks contains a function (the run-event emitter). The checkpoint could not be written, the graph raised an error outside any phase, nothing marked the run as failed, and the queue started it again, without end.

The first-increment tests did not show it: the unit tests used a simple state, and the one end-to-end test that goes through the graph (`test_stream_completes_after_approve_with_persisted_events`) skips itself when the stream takes more than 10 seconds, so it was reported as skipped, not failed.

Fixes in `src/workflows/agent_graph.py`:

- `_storable` keeps the data in the carried variables and leaves out what the checkpoint store cannot write (functions and other live objects).
- If the graph still fails outside a phase, the run is recorded as failed once, and its checkpoints are removed.

The restart test also showed LangGraph warning that it will soon refuse to restore application types kept in the state (branding and content-enrichment objects). They are now listed in `CHECKPOINT_TYPES` in `src/workflows/checkpoint.py`; a test checks they restore without warnings. Add a type there if a restart log names a new one.

Limit: after a restart, the resumed phases get the stored data without the live objects. The checks and finalize phases read plain data from the state (`qa_report`, `guardrail_report`, `unified_quality_reports`, `memory_summary`, `fallback_applied`), but this has only been tested with a simulated restart.

## What this does not do yet

| Item | Why it matters | Where it would go |
|---|---|---|
| Finer nodes inside generate | Generate is still one node that wraps the whole coordinator (planning, parallel document agents, QA loop). A crash during generation restarts generation | Split the coordinator's `coordinate()` into plan, per-deliverable generate (parallel branches) and QA nodes |
| Approval gates as graph interrupts | Plan approval and final review are still run statuses outside the graph | `interrupt()` before generate and after finalize, with the API resuming the thread |
| Remediation as a loop edge | Remediation re-queues the run and starts a new thread | A conditional edge from evaluate back to generate |
| Pause and resume flags | Still the existing `pause_requested` / `resume_requested` columns | Interrupts |
| Sheldon's conversation | First increment done: four turn phases, a graph driver and background replies | See `conversation-graph.md` |
| Memory recall as a node | Long-term memory is still read inside the coordinator's own context assembly | Move the `assemble_v2` call into the context phase |

These are ordered by value: finer generate nodes give the largest resilience gain, and the approval interrupts give the cleanest design.
