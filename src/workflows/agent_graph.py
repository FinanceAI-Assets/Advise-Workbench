"""Run execution as a LangGraph graph: prepare -> generate -> evaluate -> finalize.

Each node runs one phase from ``src.workflows.orchestrator`` unchanged, so the graph and the legacy
orchestrator share all run logic. What the graph adds is a checkpoint after every phase: when the
server restarts mid-run, the run continues from the last finished phase instead of failing, so a
crash during the checks does not repeat the generation.

A phase that ends the attempt (run failed, run re-queued for remediation, run finished) returns an
outcome, and the graph stops there. Remediation re-queues the run, which starts a new graph thread,
so every attempt has its own checkpoints.
"""

from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph
from sqlalchemy import func, select

from src.core.db.models import RunEvent
from src.core.db.session import SessionLocal
from src.core.observability.otel_tracing import start_span
from src.workflows import orchestrator
from src.workflows.checkpoint import checkpoint_serde, get_checkpointer

_LOG = logging.getLogger(__name__)
_SERDE = checkpoint_serde()
PHASE_ORDER = ("prepare", "context", "generate", "evaluate", "remember", "finalize")

# The job a graph thread is working on. A job holds a database session and ORM objects, which cannot
# be checkpointed; after a restart it is rebuilt from the checkpointed variables (see _job_for).
_LIVE_JOBS: dict[str, orchestrator.RunJob] = {}
_LIVE_LOCK = threading.Lock()


class RunGraphState(TypedDict, total=False):
    project_id: str
    run_id: str
    queue_payload: dict[str, Any] | None
    thread_id: str
    completed: list[str]  # phases finished in this attempt
    carry: dict[str, Any]  # variables later phases need, in JSON form
    outcome: list[Any] | None  # [ok, error] once the attempt has ended


_DROP = object()
_PLAIN = (str, int, float, bool, type(None))


def _storable(value: Any) -> Any:
    """A copy of ``value`` that the checkpoint store can write; what it cannot write is left out.

    The coordinator state holds live objects next to its data (for example the function that emits
    run events). A checkpoint that cannot be written stops the whole run, so those are dropped here.
    They are only missed when a run is resumed after a restart; a run that is not interrupted keeps
    using the live job and never reads the checkpointed copy.
    """
    if isinstance(value, _PLAIN):
        return value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {k: kept for k, v in value.items() if isinstance(k, _PLAIN) and (kept := _storable(v)) is not _DROP}
    if isinstance(value, (list, tuple, set)):
        return [kept for v in value if (kept := _storable(v)) is not _DROP]
    if callable(value):
        return _DROP
    try:
        _SERDE.dumps_typed(value)
    except Exception:  # noqa: BLE001 — anything the store cannot encode
        return _DROP
    return value


def _snapshot(job: orchestrator.RunJob, after_phase: str) -> dict[str, Any]:
    """The variables the remaining phases need, taken from the job after ``after_phase``."""
    names: set[str] = set()
    for phase in PHASE_ORDER[PHASE_ORDER.index(after_phase) + 1 :]:
        names.update(orchestrator.PHASE_CARRY.get(phase, ()))
    return {name: kept for name in sorted(names) if name in job.vars and (kept := _storable(job.vars[name])) is not _DROP}


def _job_for(state: RunGraphState) -> orchestrator.RunJob | None:
    """The live job for this thread, rebuilt from the checkpoint when the process was restarted.

    Returns None when the rebuilt job cannot continue (for example the run was cancelled meanwhile);
    the outcome is then already recorded on the returned state by the caller.
    """
    thread_id = state["thread_id"]
    with _LIVE_LOCK:
        job = _LIVE_JOBS.get(thread_id)
    if job is not None:
        return job
    job = orchestrator.RunJob(project_id=state["project_id"], run_id=state["run_id"], queue_payload=state.get("queue_payload"))
    orchestrator.open_run_job(job)
    with _LIVE_LOCK:
        _LIVE_JOBS[thread_id] = job
    if state.get("completed"):
        # Resuming after a restart: reload the run and re-check admission, then restore the phase variables.
        outcome = orchestrator._phase_prepare(job)
        if outcome is not None:
            job.vars["_resume_outcome"] = outcome
            return job
        carry = dict(state.get("carry") or {})
        if isinstance(carry.get("run_dir"), str):
            carry["run_dir"] = Path(carry["run_dir"])
        job.vars.update(carry)
        _LOG.info("run graph: resumed run %s after %s", job.run_id, ", ".join(state["completed"]))
    return job


def _phase_node(name: str):
    phase = dict(orchestrator.RUN_PHASES)[name]

    def node(state: RunGraphState) -> RunGraphState:
        job = _job_for(state)
        resume_outcome = job.vars.pop("_resume_outcome", None)
        if resume_outcome is not None:
            return {"outcome": list(resume_outcome)}
        attributes = {"run_id": job.run_id, "project_id": job.project_id, "graph.thread_id": state.get("thread_id") or ""}
        with start_span(f"run.phase.{name}", attributes=attributes) as span:
            if name == "prepare":
                outcome = phase(job)  # an error here is not turned into a failed run
            else:
                try:
                    outcome = phase(job)
                except Exception as exc:  # noqa: BLE001 — surface as run failure
                    outcome = orchestrator.fail_run_job(job, exc)
            if outcome is not None:
                span.set_attribute("run.outcome_ok", bool(outcome[0]))
                span.set_attribute("run.outcome_error", str(outcome[1] or "")[:300])
        update: RunGraphState = {"completed": [*state.get("completed", []), name]}
        if outcome is not None:
            update["outcome"] = list(outcome)
        elif name != PHASE_ORDER[-1]:
            update["carry"] = _snapshot(job, name)
        return update

    return node


def _next_after(name: str):
    following = PHASE_ORDER[PHASE_ORDER.index(name) + 1]

    def route(state: RunGraphState) -> str:
        return END if state.get("outcome") is not None else following

    return route


def build_run_graph(checkpointer: Any = None) -> Any:
    graph = StateGraph(RunGraphState)
    for name in PHASE_ORDER:
        graph.add_node(name, _phase_node(name))
    graph.add_edge(START, PHASE_ORDER[0])
    for name in PHASE_ORDER[:-1]:
        graph.add_conditional_edges(name, _next_after(name), [PHASE_ORDER[PHASE_ORDER.index(name) + 1], END])
    graph.add_edge(PHASE_ORDER[-1], END)
    return graph.compile(checkpointer=checkpointer)


def thread_id_for(run_id: str) -> str:
    """One graph thread per attempt: remediation re-queues the run and starts a fresh thread."""
    session = SessionLocal()
    try:
        attempt = int(
            session.scalar(
                select(func.count()).select_from(RunEvent).where(RunEvent.run_id == run_id, RunEvent.event_type == "evaluator_retry_requested")
            )
            or 0
        )
    finally:
        session.close()
    return f"{run_id}:attempt-{attempt}"


def has_unfinished_attempt(run_id: str) -> bool:
    """True when the current attempt has a checkpoint with phases still to run (the server stopped mid-run)."""
    try:
        snapshot = build_run_graph(get_checkpointer()).get_state({"configurable": {"thread_id": thread_id_for(run_id)}})
    except Exception as exc:  # noqa: BLE001 — a missing or unreadable store means nothing to resume
        _LOG.warning("run graph: could not read checkpoint for %s: %s", run_id, exc)
        return False
    return bool(snapshot.next) and bool((snapshot.values or {}).get("completed"))


def execute_run_with_graph(project_id: str, run_id: str, queue_payload: dict[str, Any] | None = None) -> orchestrator.RunOutcome:
    """Run one attempt through the graph, continuing from its checkpoint when one exists."""
    thread_id = thread_id_for(run_id)
    config = {"configurable": {"thread_id": thread_id}}
    graph = build_run_graph(get_checkpointer())
    snapshot = graph.get_state(config)
    try:
        if snapshot.next:  # an earlier process stopped part-way through this attempt
            final = graph.invoke(None, config, durability="sync")
        else:
            final = graph.invoke(
                {"project_id": project_id, "run_id": run_id, "queue_payload": queue_payload, "thread_id": thread_id, "completed": []},
                config,
                durability="sync",  # write each checkpoint before the next phase starts
            )
    except Exception as exc:  # noqa: BLE001 — the graph itself failed (for example a checkpoint could not be written)
        _LOG.exception("run graph: attempt %s stopped outside a phase", thread_id)
        with _LIVE_LOCK:
            job = _LIVE_JOBS.get(thread_id)
        if job is None or job.vars.get("session") is None:
            raise
        # Without this the run would stay "running" and the queue would start it again, for ever.
        final = {"outcome": list(orchestrator.fail_run_job(job, exc))}
    finally:
        with _LIVE_LOCK:
            job = _LIVE_JOBS.pop(thread_id, None)
        if job is not None and job.vars.get("session") is not None:
            job.vars["session"].close()
    _forget_attempt(thread_id)  # the attempt ran to its end; its checkpoints are no longer needed
    outcome = final.get("outcome")
    return (bool(outcome[0]), outcome[1]) if outcome else (True, None)


def _forget_attempt(thread_id: str) -> None:
    try:
        get_checkpointer().delete_thread(thread_id)
    except Exception as exc:  # noqa: BLE001 — housekeeping only
        _LOG.warning("run graph: could not delete checkpoints for %s: %s", thread_id, exc)
