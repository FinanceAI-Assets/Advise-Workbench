"""Drives one conversation turn through its phases as a LangGraph graph.

The phases themselves belong to the caller (see ``TURN_PHASES`` in
``src/app/api/projects/conversation.py``). A phase takes the turn and returns the reply when it
ends the turn, or None to continue. Nothing is checkpointed: a turn lives inside one request, and
the conversation's lasting state is already stored on the conversation row.
"""

from __future__ import annotations

from collections.abc import Callable
from functools import lru_cache
from typing import Any, TypedDict

from src.core.observability.otel_tracing import start_span

Phase = Callable[[Any], dict | None]
Phases = tuple[tuple[str, Phase], ...]


class TurnGraphState(TypedDict, total=False):
    turn: Any
    on_phase: Callable[[str], None] | None
    reply: dict | None


def _node(name: str, phase: Phase) -> Callable[[TurnGraphState], dict]:
    def run(state: TurnGraphState) -> dict:
        if state.get("on_phase"):
            state["on_phase"](name)
        with start_span(f"conversation.phase.{name}"):
            return {"reply": phase(state["turn"])}

    return run


@lru_cache(maxsize=4)
def build_turn_graph(phases: Phases) -> Any:
    from langgraph.graph import END, START, StateGraph

    names = [name for name, _ in phases]
    graph = StateGraph(TurnGraphState)
    for name, phase in phases:
        graph.add_node(name, _node(name, phase))
    graph.add_edge(START, names[0])
    for here, after in zip(names, names[1:], strict=False):
        graph.add_conditional_edges(
            here, lambda s, after=after: END if s.get("reply") is not None else after, [after, END]
        )
    graph.add_edge(names[-1], END)
    return graph.compile()


def run_turn(phases: Phases, turn: Any, on_phase: Callable[[str], None] | None = None) -> dict:
    """Run the phases in order until one returns the reply."""
    with start_span("conversation.turn", attributes={"project_id": str(getattr(turn, "pid", "") or "")}):
        reply = build_turn_graph(phases).invoke({"turn": turn, "on_phase": on_phase, "reply": None}).get("reply")
    if reply is None:
        raise RuntimeError("conversation turn ended without a reply")
    return reply
