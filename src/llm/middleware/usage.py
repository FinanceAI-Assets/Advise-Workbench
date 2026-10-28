"""The single place LLM usage is charged to the run/project budget and reported to metrics and tracing."""

from __future__ import annotations

from typing import Any

from src.core.observability.metrics import increment
from src.llm.run_budget import charge_llm_usage


def usage_counts(message: Any) -> dict[str, int]:
    usage = getattr(message, "usage", None)

    def read(name: str) -> int:
        return int(getattr(usage, name, 0) or 0) if usage is not None else 0

    return {
        "input_tokens": read("input_tokens"),
        "output_tokens": read("output_tokens"),
        "cache_read_tokens": read("cache_read_input_tokens"),
        "cache_creation_tokens": read("cache_creation_input_tokens"),
    }


def record_usage(message: Any, span: Any = None) -> dict[str, int]:
    """Charge the budget (may raise ``RunBudgetExceeded``), bump metrics and annotate ``span``."""
    counts = usage_counts(message)
    if span is not None:
        span.set_attribute("gen_ai.usage.input_tokens", counts["input_tokens"])
        span.set_attribute("gen_ai.usage.output_tokens", counts["output_tokens"])
        span.set_attribute("gen_ai.response.finish_reason", str(getattr(message, "stop_reason", "") or ""))
    increment("llm_calls_total")
    increment("llm_input_tokens_total", counts["input_tokens"])
    increment("llm_output_tokens_total", counts["output_tokens"])
    if any(counts.values()):
        charge_llm_usage(**counts)
    return counts
