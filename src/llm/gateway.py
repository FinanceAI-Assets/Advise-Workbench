"""The one place the app asks for a model. Pick the provider with ``LLM_PROVIDER`` in .env.

``create_message`` takes Anthropic Messages API arguments and returns a message with ``content`` blocks,
``stop_reason`` and ``usage`` whatever the provider. ``capabilities()`` tells callers what the provider
can do so they can degrade (no tools -> single call, no vision -> skip image checks, no thinking -> plain call).

Every call runs through the same pipeline: tracing span -> circuit breaker -> retry with backoff -> provider,
then usage is charged to the run budget exactly once. When the primary provider stays unavailable and
``LLM_FALLBACK_PROVIDER`` is set, the call is replayed on the fallback.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from time import perf_counter
from typing import Any

from src.core.config import settings
from src.core.observability.metrics import observe_latency
from src.core.observability.otel_tracing import start_span
from src.llm.base_provider import BaseLLMProvider, HealthStatus
from src.llm.capabilities import Capabilities
from src.llm.config import LLMConfig, load_fallback_config, load_llm_config
from src.llm.errors import LLMConfigError, LLMError
from src.llm.factory import ProviderRegistry
from src.llm.middleware.resilience import call_with_retry, get_breaker
from src.llm.middleware.usage import record_usage

logger = logging.getLogger(__name__)

# Request fields only some providers accept; dropped when replaying a call on a fallback without thinking.
_THINKING_FIELDS = ("thinking", "output_config")


def _build(config: LLMConfig) -> BaseLLMProvider:
    return ProviderRegistry.get(config)


def get_provider() -> BaseLLMProvider:
    """The (cached) provider for the current settings. Raises ``LLMConfigError`` when not configured."""
    return _build(load_llm_config())


def provider_name() -> str:
    return load_llm_config().provider


def capabilities() -> Capabilities:
    return get_provider().capabilities


def is_enabled() -> bool:
    try:
        return bool(get_provider().is_enabled())
    except LLMConfigError:
        return False


def model_for(tier: str = "default") -> str:
    """Model name for a tier (default, planning, critique); unset tiers use the default model."""
    models = load_llm_config().models
    return models.get(tier) or models.get("default") or ""


def health() -> dict[str, Any]:
    """Provider, models, capabilities and a cheap readiness check (no tokens spent), for startup and /status."""
    try:
        config = load_llm_config()
        provider = _build(config)
        status = provider.health_check()
    except LLMConfigError as exc:
        return {"ok": False, "provider": settings.llm_provider, "detail": str(exc)}
    return {
        "ok": status.ok,
        "provider": config.label,
        "models": config.models,
        "capabilities": vars(provider.capabilities),
        "circuit_open": get_breaker(config.label).is_open,
        "fallback": settings.llm_fallback_provider or None,
        "detail": status.detail,
        **({"info": status.info} if status.info else {}),
    }


def _invoke(
    provider: BaseLLMProvider,
    call: Callable[[], Any],
    *,
    model: str,
    tools: int,
    on_event: Callable[[], None] | None,
    retry: bool,
) -> Any:
    config = provider.config
    breaker = get_breaker(config.label)
    attributes = {"gen_ai.system": config.label, "gen_ai.request.model": model, "llm.tools": tools}
    started = perf_counter()
    with start_span("llm.call", attributes=attributes) as span:
        breaker.before_call()
        try:
            if retry:
                message = call_with_retry(call, max_retries=max(0, int(settings.llm_max_retries)), on_event=on_event)
            else:
                message = call()
        except LLMError as exc:
            if exc.retryable:
                breaker.record_failure()
            raise
        breaker.record_success()
        observe_latency("llm_call", (perf_counter() - started) * 1000.0)
        record_usage(message, span)
    return message


def _fallback_provider(primary: BaseLLMProvider, kwargs: dict[str, Any], beta: bool) -> BaseLLMProvider | None:
    """The fallback provider, if one is set and can serve this request."""
    try:
        config = load_fallback_config()
    except LLMConfigError as exc:
        logger.error("LLM_FALLBACK_PROVIDER is set but not usable: %s", exc)
        return None
    if config is None or config.fingerprint == primary.config.fingerprint:
        return None
    fallback = _build(config)
    caps = fallback.capabilities
    if not fallback.is_enabled():
        return None
    if beta and not caps.anthropic_tools:
        return None
    if kwargs.get("tools") and (not caps.tools or caps.delegated_tools):
        return None  # a tool loop in progress needs a provider that returns tool_use blocks
    return fallback


def create_message(*, stream: bool = False, beta: bool = False, on_event: Callable[[], None] | None = None, **kwargs: Any) -> Any:
    provider = get_provider()

    def call_on(target: BaseLLMProvider, request: dict[str, Any]) -> Any:
        return _invoke(
            target,
            lambda: target.create_message(stream=stream, beta=beta, on_event=on_event, **request),
            model=str(request.get("model") or ""),
            tools=len(request.get("tools") or []),
            on_event=on_event,
            retry=True,
        )

    try:
        return call_on(provider, kwargs)
    except LLMError as exc:
        if not exc.retryable:
            raise
        fallback = _fallback_provider(provider, kwargs, beta)
        if fallback is None:
            raise
        logger.warning("LLM provider %s unavailable (%s); using fallback %s", provider.config.label, exc, fallback.config.label)
        request = dict(kwargs, model=fallback.config.models.get("default") or "")
        if not fallback.capabilities.thinking:
            for name in _THINKING_FIELDS:
                request.pop(name, None)
        return call_on(fallback, request)


def run_tool_session(*, on_event: Callable[[], None] | None = None, **kwargs: Any) -> Any:
    """Delegated tool loop (``capabilities().delegated_tools``): the provider calls the app's tools itself.

    Not retried, because tools may already have run (writes are not idempotent); usage is charged once
    for the whole session.
    """
    provider = get_provider()
    if not provider.capabilities.delegated_tools:
        raise LLMConfigError(f"{provider.config.label} does not run tool sessions; use create_message with tools")
    return _invoke(
        provider,
        lambda: provider.run_tool_session(on_event=on_event, **kwargs),
        model=str(kwargs.get("model") or ""),
        tools=len(kwargs.get("tools") or []),
        on_event=on_event,
        retry=False,
    )


__all__ = [
    "HealthStatus",
    "capabilities",
    "create_message",
    "get_provider",
    "health",
    "is_enabled",
    "model_for",
    "provider_name",
    "run_tool_session",
]
