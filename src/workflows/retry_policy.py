"""Run retry/recovery helpers for execution and evaluator stages."""

from __future__ import annotations

import random
from typing import Any


def classify_retry_mode(*, retry_after_sec: float | None, cooldown_threshold_sec: float = 20.0) -> str:
    if retry_after_sec is not None and float(retry_after_sec) >= float(cooldown_threshold_sec):
        return "cooldown_retry"
    return "fast_retry"


def compute_rate_limit_backoff(*, retry_after_sec: float | None, attempt: int, base_sec: float, max_sec: float) -> float:
    """Mode A: honor Retry-After when present, otherwise exponential + jitter."""
    if retry_after_sec is not None and retry_after_sec > 0:
        return float(min(max_sec, max(0.5, retry_after_sec)))
    exp = base_sec * (2 ** max(0, attempt - 1))
    jitter = random.uniform(0.0, min(1.5, base_sec))  # noqa: S311 — non-cryptographic backoff jitter
    return float(min(max_sec, max(0.5, exp + jitter)))


def should_apply_fallback(*, consecutive_failures: int, threshold: int = 3) -> bool:
    """Mode B: trigger fallback path after repeated failures."""
    return int(consecutive_failures) >= int(threshold)


def overflow_recovery_event(*, token_budget: int | None = None, char_cap: int | None = None, applied_tier: str = "") -> dict[str, Any]:
    """Mode C: typed payload for context overflow recovery."""
    # Workstream A: support both token_budget (new) and char_cap (legacy)
    if token_budget is None and char_cap is not None:
        token_budget = int(char_cap / 3.5)
    # Old code (kept for reference):
    # return {
    #     "mode": "context_overflow_recovery",
    #     "char_cap": int(char_cap),
    #     "applied_tier": str(applied_tier),
    # }
    return {
        "mode": "context_overflow_recovery",
        "token_budget": int(token_budget or 32000),
        "applied_tier": str(applied_tier),
    }


def heartbeat_event(*, run_id: str, phase: str) -> dict[str, Any]:
    """Mode D: long-run heartbeat payload."""
    return {"run_id": run_id, "phase": phase, "mode": "heartbeat"}


def fallback_strategy_for_output(output_type: str) -> dict[str, Any]:
    ot = str(output_type or "").strip().lower()
    if ot in {"pptx", "docx", "pdf"}:
        return {"mode": "degrade_fidelity", "max_rounds": 1}
    if ot in {"xlsx", "process_map"}:
        return {"mode": "deterministic_template", "max_rounds": 1}
    return {"mode": "default", "max_rounds": 1}


RETRY_FSM_ALLOWED: dict[str, set[str]] = {
    "scheduled": {"executing"},
    # After failure the worker was executing; a retry re-queues as scheduled.
    "executing": {"recovered", "exhausted", "dead_letter", "scheduled"},
    "recovered": set(),
    "exhausted": set(),
    "dead_letter": set(),
}


def validate_retry_transition(current_state: str, next_state: str) -> bool:
    cur = str(current_state or "").strip().lower()
    nxt = str(next_state or "").strip().lower()
    return nxt in RETRY_FSM_ALLOWED.get(cur, set())

