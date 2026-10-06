"""The one place the app asks for a model. Pick the provider in config/model_config.yaml or LLM_PROVIDER.

``create_message`` takes Anthropic Messages API arguments and returns a message with ``content`` blocks,
``stop_reason`` and ``usage`` whatever the provider. ``capabilities()`` tells callers what the provider
can do so they can degrade (no tools -> single call, no vision -> skip image checks, no thinking -> plain call).
"""

from __future__ import annotations

from collections.abc import Callable
from time import perf_counter
from typing import Any

from src.core.observability.metrics import increment, observe_latency
from src.core.observability.otel_tracing import start_span
from src.llm.capabilities import Capabilities
from src.llm.config import LLMConfig, load_llm_config


def _build(config: LLMConfig) -> Any:
    if config.provider == "claude_cli":
        from src.llm.providers.claude_cli import ClaudeCliProvider

        return ClaudeCliProvider(config)
    if config.provider == "openai_compatible":
        from src.llm.providers.openai_compatible import OpenAICompatibleProvider

        return OpenAICompatibleProvider(config)
    from src.llm.providers.anthropic_api import AnthropicProvider

    return AnthropicProvider(config)


def get_provider() -> Any:
    """Provider for the current settings. Built per call: it is cheap, and tests change settings at run time."""
    return _build(load_llm_config())


def provider_name() -> str:
    return load_llm_config().provider


def capabilities() -> Capabilities:
    return get_provider().capabilities


def is_enabled() -> bool:
    return bool(get_provider().is_enabled())


def model_for(tier: str = "default") -> str:
    """Model name for a tier (default, planning, critique): configured value, else the provider's own default."""
    config = load_llm_config()
    defaults = _build(config).default_models
    for candidate in (config.models.get(tier), defaults.get(tier), config.models.get("default"), defaults.get("default")):
        if candidate:
            return candidate
    return ""


def create_message(*, stream: bool = False, beta: bool = False, on_event: Callable[[], None] | None = None, **kwargs: Any) -> Any:
    provider = get_provider()
    attributes = {"gen_ai.system": provider.name, "gen_ai.request.model": str(kwargs.get("model") or ""), "llm.tools": len(kwargs.get("tools") or [])}
    started = perf_counter()
    with start_span("llm.call", attributes=attributes) as span:
        message = provider.create_message(stream=stream, beta=beta, on_event=on_event, **kwargs)
        usage = getattr(message, "usage", None)
        tokens_in = int(getattr(usage, "input_tokens", 0) or 0)
        tokens_out = int(getattr(usage, "output_tokens", 0) or 0)
        span.set_attribute("gen_ai.usage.input_tokens", tokens_in)
        span.set_attribute("gen_ai.usage.output_tokens", tokens_out)
        span.set_attribute("gen_ai.response.finish_reason", str(getattr(message, "stop_reason", "") or ""))
    observe_latency("llm_call", (perf_counter() - started) * 1000.0)
    increment("llm_calls_total")
    increment("llm_input_tokens_total", tokens_in)
    increment("llm_output_tokens_total", tokens_out)
    return message
