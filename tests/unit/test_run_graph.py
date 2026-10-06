"""LangGraph run orchestrator: phase order, early stop, failure handling and resume after a restart."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.core.config import settings
from src.core.db.session import init_db
from src.workflows import agent_graph, checkpoint, orchestrator


class _ProcessDied(BaseException):
    """Stands in for the server stopping mid-phase (not an Exception, so nothing handles it)."""


@pytest.fixture
def graph_env(tmp_path, monkeypatch: pytest.MonkeyPatch):
    init_db()
    monkeypatch.setattr(settings, "workspace_root", str(tmp_path))
    checkpoint.reset_checkpointer()
    calls: list[str] = []
    behaviour: dict[str, object] = {}

    def phase(name: str):
        def run(job: orchestrator.RunJob):
            calls.append(name)
            action = behaviour.get(name)
            if isinstance(action, BaseException):
                raise action
            if name == "generate":
                job.vars.update(state={"narrative_md": "# Draft"}, run_todos=[{"id": "qa"}], run_dir=tmp_path / "runs" / job.run_id, requested=["docx"])
            if name == "evaluate":
                behaviour["evaluate_saw"] = {k: job.vars.get(k) for k in ("state", "run_todos", "run_dir", "requested")}
            if name == "finalize":
                return True, None
            return action  # None, or an outcome tuple that ends the attempt

        return run

    monkeypatch.setattr(orchestrator, "RUN_PHASES", tuple((n, phase(n)) for n in agent_graph.PHASE_ORDER))
    monkeypatch.setattr(orchestrator, "_phase_prepare", dict(orchestrator.RUN_PHASES)["prepare"])
    yield calls, behaviour
    agent_graph._LIVE_JOBS.clear()
    checkpoint.reset_checkpointer()


def test_phases_run_in_order(graph_env) -> None:
    calls, _ = graph_env
    assert agent_graph.execute_run_with_graph("p_1", "run_order") == (True, None)
    assert calls == ["prepare", "context", "generate", "evaluate", "remember", "finalize"]
    assert agent_graph.has_unfinished_attempt("run_order") is False
    assert agent_graph._LIVE_JOBS == {}


def test_a_phase_outcome_ends_the_attempt(graph_env) -> None:
    calls, behaviour = graph_env
    behaviour["evaluate"] = (False, "Evaluator checks failed")
    assert agent_graph.execute_run_with_graph("p_1", "run_stop") == (False, "Evaluator checks failed")
    assert calls == ["prepare", "context", "generate", "evaluate"]


def test_an_error_in_a_phase_is_recorded_as_a_failed_run(graph_env, monkeypatch: pytest.MonkeyPatch) -> None:
    calls, behaviour = graph_env
    behaviour["generate"] = RuntimeError("model unavailable")
    seen: list[str] = []
    monkeypatch.setattr(orchestrator, "fail_run_job", lambda job, exc: seen.append(str(exc)) or (False, str(exc)))
    assert agent_graph.execute_run_with_graph("p_1", "run_error") == (False, "model unavailable")
    assert seen == ["model unavailable"] and calls == ["prepare", "context", "generate"]


def test_restart_resumes_after_the_last_finished_phase(graph_env, tmp_path) -> None:
    calls, behaviour = graph_env
    behaviour["evaluate"] = _ProcessDied()
    with pytest.raises(_ProcessDied):
        agent_graph.execute_run_with_graph("p_1", "run_resume")
    assert calls == ["prepare", "context", "generate", "evaluate"]
    assert agent_graph.has_unfinished_attempt("run_resume") is True

    # "Restart": nothing survives in memory, only the checkpoint file.
    agent_graph._LIVE_JOBS.clear()
    checkpoint.reset_checkpointer()
    calls.clear()
    behaviour.pop("evaluate")

    assert agent_graph.execute_run_with_graph("p_1", "run_resume") == (True, None)
    assert calls == ["prepare", "evaluate", "remember", "finalize"]  # admission is re-checked; generation is not repeated
    saw = behaviour["evaluate_saw"]
    assert saw["state"] == {"narrative_md": "# Draft"} and saw["run_todos"] == [{"id": "qa"}] and saw["requested"] == ["docx"]
    assert saw["run_dir"] == Path(tmp_path / "runs" / "run_resume")
    assert agent_graph.has_unfinished_attempt("run_resume") is False


def test_restart_during_generation_keeps_the_assembled_context(graph_env, monkeypatch: pytest.MonkeyPatch) -> None:
    calls, behaviour = graph_env
    phases = dict(orchestrator.RUN_PHASES)
    original_generate = phases["generate"]
    seen: dict[str, object] = {}

    def context(job: orchestrator.RunJob):
        calls.append("context")
        job.vars.update(init_state={"conversation_digest": "Client wants a 10-slide deck"}, requested=["pptx"], output_type_representations={}, hard_gate_enabled=True)

    def generate(job: orchestrator.RunJob):
        seen.update({k: job.vars.get(k) for k in ("init_state", "requested", "hard_gate_enabled")})
        return original_generate(job)

    phases |= {"context": context, "generate": generate}
    monkeypatch.setattr(orchestrator, "RUN_PHASES", tuple((n, phases[n]) for n in agent_graph.PHASE_ORDER))
    behaviour["generate"] = _ProcessDied()
    with pytest.raises(_ProcessDied):
        agent_graph.execute_run_with_graph("p_1", "run_ctx")
    agent_graph._LIVE_JOBS.clear()
    checkpoint.reset_checkpointer()
    calls.clear()
    seen.clear()
    behaviour.pop("generate")

    assert agent_graph.execute_run_with_graph("p_1", "run_ctx") == (True, None)
    assert calls == ["prepare", "generate", "evaluate", "remember", "finalize"]  # the context is not assembled again
    assert seen == {"init_state": {"conversation_digest": "Client wants a 10-slide deck"}, "requested": ["pptx"], "hard_gate_enabled": True}


def test_resume_stops_when_the_run_can_no_longer_continue(graph_env) -> None:
    calls, behaviour = graph_env
    behaviour["evaluate"] = _ProcessDied()
    with pytest.raises(_ProcessDied):
        agent_graph.execute_run_with_graph("p_1", "run_cancelled")
    agent_graph._LIVE_JOBS.clear()
    calls.clear()
    behaviour.pop("evaluate")
    behaviour["prepare"] = (False, "Aborted via persisted control_state before execution.")  # cancelled while the server was down

    assert agent_graph.execute_run_with_graph("p_1", "run_cancelled") == (False, "Aborted via persisted control_state before execution.")
    assert calls == ["prepare"]


def test_queued_runs_go_through_the_graph(graph_env) -> None:
    calls, _ = graph_env
    assert orchestrator._execute_run_job("p_1", "run_switch") == (True, None)
    assert calls == ["prepare", "context", "generate", "evaluate", "remember", "finalize"]


def test_snapshot_keeps_data_and_leaves_out_what_cannot_be_stored(tmp_path) -> None:
    from dataclasses import dataclass

    @dataclass
    class Branding:
        colour: str

    job = orchestrator.RunJob(project_id="p_1", run_id="run_snap")
    job.vars.update(
        state={"qa_report": {"passed": True}, "_emit_run_event": lambda *a: None, "branding": Branding("#86BC24"), "items": [1, print]},
        run_todos=[{"id": "qa"}],
        run_dir=tmp_path / "runs" / "run_snap",
        requested=["docx"],
    )
    snap = agent_graph._snapshot(job, "generate")
    assert snap["state"]["qa_report"] == {"passed": True}
    assert "_emit_run_event" not in snap["state"] and snap["state"]["items"] == [1]
    assert snap["run_dir"] == str(tmp_path / "runs" / "run_snap")
    agent_graph._SERDE.dumps_typed(snap)  # the checkpoint store can write it


def test_live_objects_in_the_state_do_not_stop_the_run(graph_env, monkeypatch: pytest.MonkeyPatch) -> None:
    """The coordinator state carries a function; the run must still reach its end."""
    calls, _ = graph_env
    generate = dict(orchestrator.RUN_PHASES)["generate"]

    def generate_with_live_objects(job: orchestrator.RunJob):
        generate(job)
        job.vars["state"]["_emit_run_event"] = lambda *a: None

    phases = dict(orchestrator.RUN_PHASES) | {"generate": generate_with_live_objects}
    monkeypatch.setattr(orchestrator, "RUN_PHASES", tuple((n, phases[n]) for n in agent_graph.PHASE_ORDER))
    assert agent_graph.execute_run_with_graph("p_1", "run_live") == (True, None)
    assert calls == ["prepare", "context", "generate", "evaluate", "remember", "finalize"]


def test_a_checkpoint_that_cannot_be_written_fails_the_run_once(graph_env, monkeypatch: pytest.MonkeyPatch) -> None:
    calls, _ = graph_env
    seen: list[str] = []
    monkeypatch.setattr(agent_graph, "_snapshot", lambda job, after: {"bad": lambda: None})
    monkeypatch.setattr(orchestrator, "fail_run_job", lambda job, exc: seen.append(type(exc).__name__) or (False, str(exc)))
    ok, error = agent_graph.execute_run_with_graph("p_1", "run_badcp")
    assert ok is False and "serializable" in str(error)
    assert len(seen) == 1 and calls == ["prepare"]  # the first checkpoint is written after prepare
    assert agent_graph._LIVE_JOBS == {} and agent_graph.has_unfinished_attempt("run_badcp") is False


def test_run_started_through_the_api_reaches_an_end_under_the_graph(monkeypatch: pytest.MonkeyPatch) -> None:
    """End to end with the real phases: the run must finish (review or failed checks), not hang."""
    import time

    from fastapi.testclient import TestClient

    from src.app.main import app as fastapi_app
    from tests.unit.plan_helpers import confirm_plan_for_project
    from tests.unit.test_auth_hitl import auth_header

    from src.guardrails import hooks

    # Other tests leave hooks registered that fail on purpose and would abort this run before it starts.
    monkeypatch.setattr(hooks, "_HOOK_REGISTRY_PLATFORM", {point: [] for point in hooks._HOOK_REGISTRY_PLATFORM})
    monkeypatch.setattr(hooks, "_HOOK_REGISTRY_PROJECT", {})
    checkpoint.reset_checkpointer()
    client = TestClient(fastapi_app)
    headers = auth_header(client, email="graph-e2e@example.com")
    pid = client.post("/api/projects", json={"name": "Graph end to end"}, headers=headers).json()["id"]
    conv_id, plan_hash = confirm_plan_for_project(client, headers, pid)
    started = client.post(
        "/api/runs",
        json={"project_id": pid, "conversation_id": conv_id, "plan_hash": plan_hash, "instruction": "Complete run"},
        headers=headers,
    )
    run_id = started.json()["run_id"]
    assert client.post(f"/api/runs/{pid}/{run_id}/approve", headers=headers).status_code == 200

    kinds: list[str] = []
    deadline = time.time() + 60
    while time.time() < deadline:
        events = client.get(f"/api/runs/{pid}/{run_id}/events", headers=headers).json()
        kinds = [item.get("event_type") for item in (events.get("items", []) if isinstance(events, dict) else events)]
        if "review_ready" in kinds or "failed" in kinds:
            break
        time.sleep(0.25)
    assert "review_ready" in kinds or "failed" in kinds, kinds[-8:]
    assert "qa_report" in kinds  # generation and the checks both ran
    checkpoint.reset_checkpointer()


def test_run_state_types_are_restored_without_warnings(caplog: pytest.LogCaptureFixture) -> None:
    """Types the coordinator keeps in the state must be on the allowlist, or a resume will break in later LangGraph versions."""
    import importlib
    import logging

    for module, name in checkpoint.CHECKPOINT_TYPES:
        assert hasattr(importlib.import_module(module), name), (module, name)
    from src.agents.content_enrichment import UserIntent
    from src.deliverables.branding_service import BrandingLevel

    serde = checkpoint.checkpoint_serde()
    value = {"intent": list(UserIntent)[0], "level": list(BrandingLevel)[0]}
    with caplog.at_level(logging.WARNING):
        restored = serde.loads_typed(serde.dumps_typed(value))
    assert restored == value
    assert "unregistered type" not in caplog.text
