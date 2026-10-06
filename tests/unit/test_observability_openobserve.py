"""OpenObserve telemetry: where it is sent, which spans are opened, and metrics forwarding."""

from __future__ import annotations

import base64
from contextlib import contextmanager
from types import SimpleNamespace

import pytest

from src.core.config import settings
from src.core.observability import metrics, otel_tracing
from src.llm import gateway
from src.workflows import agent_graph, conversation_graph
from tests.unit.test_run_graph import graph_env  # noqa: F401 — fixture


def _record_spans(monkeypatch: pytest.MonkeyPatch, module) -> list[tuple[str, dict]]:
    seen: list[tuple[str, dict]] = []

    @contextmanager
    def fake_span(name: str, *, attributes: dict | None = None):
        attrs = dict(attributes or {})
        seen.append((name, attrs))
        yield SimpleNamespace(set_attribute=attrs.__setitem__)

    monkeypatch.setattr(module, "start_span", fake_span)
    return seen


def test_openobserve_target_uses_the_org_stream_and_basic_auth(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "openobserve_url", "http://oo.example:5080/")
    monkeypatch.setattr(settings, "openobserve_org", "team")
    monkeypatch.setattr(settings, "openobserve_user", "a@b.c")
    monkeypatch.setattr(settings, "openobserve_password", "secret")
    monkeypatch.setattr(settings, "openobserve_stream", "workbench")
    base, headers = otel_tracing._openobserve_target()
    assert base == "http://oo.example:5080/api/team"
    assert headers == {"Authorization": "Basic " + base64.b64encode(b"a@b.c:secret").decode(), "stream-name": "workbench"}


def test_telemetry_is_off_by_default() -> None:
    assert otel_tracing.openobserve_enabled() is False

    def work() -> int:
        return 1

    assert otel_tracing.with_trace_context(work) is work


def test_app_metrics_are_forwarded_to_the_otel_meter() -> None:
    sent: list[tuple[str, str, float]] = []

    class _Meter:
        def _make(self, kind: str, method: str):
            return lambda name: SimpleNamespace(**{method: lambda value, name=name: sent.append((kind, name, value))})

        def __getattr__(self, attr: str):
            kind = attr.removeprefix("create_")
            return self._make(kind, {"counter": "add", "histogram": "record", "gauge": "set"}[kind])

    metrics.set_otel_meter(_Meter())
    try:
        metrics.increment("run_done_total", 2)
        metrics.observe_latency("llm_call", 12.5)
        metrics.set_gauge("queue-depth", 3)
    finally:
        metrics.set_otel_meter(None)
    assert sent == [("counter", "run_done_total", 2), ("histogram", "llm_call_ms", 12.5), ("gauge", "queue_depth", 3.0)]


def test_each_run_phase_gets_a_span(graph_env, monkeypatch: pytest.MonkeyPatch) -> None:  # noqa: F811
    _, behaviour = graph_env
    behaviour["evaluate"] = (False, "Evaluator checks failed")
    seen = _record_spans(monkeypatch, agent_graph)
    agent_graph.execute_run_with_graph("p_1", "run_spans")
    assert [name for name, _ in seen] == ["run.phase.prepare", "run.phase.context", "run.phase.generate", "run.phase.evaluate"]
    last = seen[-1][1]
    assert (last["run_id"], last["project_id"], last["graph.thread_id"]) == ("run_spans", "p_1", "run_spans:attempt-0")
    assert (last["run.outcome_ok"], last["run.outcome_error"]) == (False, "Evaluator checks failed")


def test_each_conversation_phase_gets_a_span(monkeypatch: pytest.MonkeyPatch) -> None:
    seen = _record_spans(monkeypatch, conversation_graph)
    phases = (("receive", lambda turn: None), ("respond", lambda turn: {"ok": True}))
    assert conversation_graph.run_turn(phases, SimpleNamespace(pid="p_9")) == {"ok": True}
    assert seen == [("conversation.turn", {"project_id": "p_9"}), ("conversation.phase.receive", {}), ("conversation.phase.respond", {})]


def test_model_call_span_carries_model_and_token_counts(monkeypatch: pytest.MonkeyPatch) -> None:
    reply = SimpleNamespace(usage=SimpleNamespace(input_tokens=11, output_tokens=7), stop_reason="end_turn")
    provider = SimpleNamespace(name="fake", create_message=lambda **kwargs: reply)
    monkeypatch.setattr(gateway, "get_provider", lambda: provider)
    seen = _record_spans(monkeypatch, gateway)
    before = metrics.snapshot()["counters"].get("llm_input_tokens_total", 0)
    assert gateway.create_message(model="m-1", messages=[]) is reply
    assert seen == [
        (
            "llm.call",
            {
                "gen_ai.system": "fake",
                "gen_ai.request.model": "m-1",
                "llm.tools": 0,
                "gen_ai.usage.input_tokens": 11,
                "gen_ai.usage.output_tokens": 7,
                "gen_ai.response.finish_reason": "end_turn",
            },
        )
    ]
    assert metrics.snapshot()["counters"]["llm_input_tokens_total"] == before + 11
