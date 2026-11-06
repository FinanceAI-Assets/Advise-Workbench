"""Token-aware context budget: per-model token allocation for assembled context.

Replaces character-based caps with token budgets divided across system prompt, memory,
retrieved chunks, and history. Uses exact counting (Anthropic API) when available,
falls back to estimation with no impact on run execution.
"""

from __future__ import annotations

import hashlib
import logging
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

from src.core.config import settings
from src.llm.token_budgets import TokenBudgetChecker

if TYPE_CHECKING:
    from src.core.config import Settings

logger = logging.getLogger(__name__)

# Bounded token count cache: (model, sha256_hash) -> (tokens, timestamp)
_TOKEN_COUNT_CACHE: dict[tuple[str, str], tuple[int, float]] = {}
_CACHE_MAX_SIZE = 2048
_CACHE_TTL_SEC = 3600  # 1 hour

# Offline backoff: when count_tokens API fails, wait before retrying
_OFFLINE_UNTIL: float = 0.0
_OFFLINE_BACKOFF_SEC = 300  # 5 minutes

DEFAULT_CONTEXT_WINDOW = 200_000


def _text_hash(text: str) -> str:
    """SHA256 hash of text for cache key."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _clear_expired_cache() -> None:
    """Remove cache entries older than _CACHE_TTL_SEC."""
    now = time.time()
    expired = [k for k, (_, ts) in _TOKEN_COUNT_CACHE.items() if now - ts > _CACHE_TTL_SEC]
    for k in expired:
        del _TOKEN_COUNT_CACHE[k]
    # Simple eviction: if over max size, drop oldest 10%
    if len(_TOKEN_COUNT_CACHE) > _CACHE_MAX_SIZE:
        to_remove = int(_CACHE_MAX_SIZE * 0.1)
        oldest = sorted(_TOKEN_COUNT_CACHE.items(), key=lambda x: x[1][1])[:to_remove]
        for k, _ in oldest:
            del _TOKEN_COUNT_CACHE[k]


def count_tokens(text: str, model: str = "") -> tuple[int, bool]:
    """
    Count tokens in text.

    Exact counting uses Anthropic API when available; falls back to estimation.

    Args:
        text: Text to count
        model: Model name (empty for estimate-only)

    Returns:
        (token_count, is_exact): token_count is exact if is_exact=True, else estimated
    """
    if not text:
        return 0, True

    # Try exact count if offline backoff has expired
    global _OFFLINE_UNTIL
    should_try_exact = (
        model
        and settings.memory_token_count_exact
        and time.time() >= _OFFLINE_UNTIL
    )

    if should_try_exact:
        try:
            from src.llm import gateway

            provider = gateway.get_provider()
            if provider.name != "anthropic":
                # Non-Anthropic provider, use estimate
                return TokenBudgetChecker.estimate_tokens(text), False

            # Check cache
            cache_key = (model, _text_hash(text))
            if cache_key in _TOKEN_COUNT_CACHE:
                tokens, _ = _TOKEN_COUNT_CACHE[cache_key]
                return tokens, True

            # Call API
            response = provider.client.messages.count_tokens(
                model=model,
                messages=[{"role": "user", "content": text}],
            )
            tokens = response.input_tokens

            # Cache result
            _clear_expired_cache()
            _TOKEN_COUNT_CACHE[cache_key] = (tokens, time.time())

            # Workstream E: emit exact count metric
            from src.core.observability.metrics import increment
            increment("token_count_exact_total")
            return tokens, True

        except Exception as e:
            # Log at info (not error) and fall back to estimate
            logger.info(
                f"Token count API failed (starting 5-min backoff): {type(e).__name__}: {e}"
            )
            _OFFLINE_UNTIL = time.time() + _OFFLINE_BACKOFF_SEC
            # Workstream E: emit offline backoff metric
            from src.core.observability.metrics import increment
            increment("token_count_offline_backoff_started_total")
            # Fall through to estimate

    # Estimate (either explicit model="", offline backoff active, or provider error)
    # Workstream E: emit fallback metric
    from src.core.observability.metrics import increment
    increment("token_count_fallback_total")
    return TokenBudgetChecker.estimate_tokens(text), False
    # Old code (kept for reference):
    # return TokenBudgetChecker.estimate_tokens(text), False


def context_window(model: str) -> int:
    """
    Get max input tokens for a model.

    Queries Anthropic API if Anthropic provider; otherwise returns fallback.

    Args:
        model: Model name (empty for fallback)

    Returns:
        Max input tokens (200_000 if not Anthropic or API fails)
    """
    if not model:
        return DEFAULT_CONTEXT_WINDOW

    try:
        from src.llm import gateway

        provider = gateway.get_provider()
        if provider.name != "anthropic":
            return DEFAULT_CONTEXT_WINDOW

        # This is cached by the SDK
        model_info = provider.client.models.retrieve(model)
        return model_info.max_input_tokens or DEFAULT_CONTEXT_WINDOW

    except Exception as e:
        logger.info(f"Could not fetch context window for {model}: {type(e).__name__}")
        return DEFAULT_CONTEXT_WINDOW


@dataclass(frozen=True)
class MemoryBudgetPlan:
    """Token budget allocation for a single run."""

    model: str
    window: int  # max_input_tokens
    total: int  # total budget after output reserve
    system: int  # system prompt tokens (already counted or reserved)
    memory: int  # tokens for memory sections (ObjectiveNow, NonNegotiables, KnownFailures)
    retrieved: int  # tokens for evidence (retrieved chunks)
    history: int  # tokens for WhatChanged (run history)
    system_counted: bool  # True if system tokens come from actual count, not estimate

    @property
    def context_tokens(self) -> int:
        """Tokens for context sections (memory + retrieved + history)."""
        return self.memory + self.retrieved + self.history

    def as_dict(self) -> dict:
        """Serialize to dict for metadata."""
        return {
            "model": self.model,
            "window": self.window,
            "total": self.total,
            "system": self.system,
            "memory": self.memory,
            "retrieved": self.retrieved,
            "history": self.history,
            "context_tokens": self.context_tokens,
            "system_counted": self.system_counted,
        }


def plan_memory_budget(
    model: str,
    token_budget: int,
    output_reserve_tokens: int,
    system_reserve_tokens: int = 0,
    system_text: str = "",
    shares: tuple[float, float, float] = (0.40, 0.40, 0.20),
) -> MemoryBudgetPlan:
    """
    Allocate token budget across system, memory, retrieved, and history.

    Computes:
    - total = min(token_budget, window - output_reserve - 5% of window)
    - system = min(total, max(system_reserve, count(system_text)))
    - remainder split by normalised shares: memory, retrieved, history (history gets rounding)

    Args:
        model: Model name
        token_budget: Target budget (e.g. 32000)
        output_reserve_tokens: Tokens to reserve for model output (e.g. 4096)
        system_reserve_tokens: Min system tokens (0 if not set)
        system_text: System prompt text (counted if not empty)
        shares: (memory_pct, retrieved_pct, history_pct), normalized if not sum to 1

    Returns:
        MemoryBudgetPlan with token allocation
    """
    window = context_window(model)

    # Total: budget cap, window ceiling, and safety margin (5% of window)
    total = max(0, min(token_budget, window - output_reserve_tokens - int(0.05 * window)))

    # System: actual count or reserve, whichever is larger
    system_count, system_exact = count_tokens(system_text, model) if system_text else (0, True)
    system = min(total, max(system_reserve_tokens, system_count))

    # Remainder splits by normalised shares
    remainder = max(0, total - system)

    # Normalise shares
    total_share = sum(shares)
    if total_share > 0:
        norm_shares = [s / total_share for s in shares]
    else:
        norm_shares = [1 / 3, 1 / 3, 1 / 3]

    memory_share, retrieved_share, history_share = norm_shares

    # Allocate by share
    memory = int(remainder * memory_share)
    retrieved = int(remainder * retrieved_share)
    history = remainder - memory - retrieved  # History gets rounding remainder

    return MemoryBudgetPlan(
        model=model,
        window=window,
        total=total,
        system=system,
        memory=memory,
        retrieved=retrieved,
        history=history,
        system_counted=system_exact,
    )


def plan_from_settings(
    settings_obj: Settings,
    system_text: str = "",
    tier: str | None = None,
) -> MemoryBudgetPlan:
    """
    Create a budget plan from app settings.

    Uses gateway.model_for(tier) to resolve the model. Tier is inferred from
    model_tiering_enabled: if True, uses 'planning' tier (most token-hungry);
    otherwise uses 'default'.

    Args:
        settings_obj: Settings instance
        system_text: System prompt text
        tier: Override tier (default: inferred from model_tiering_enabled)

    Returns:
        MemoryBudgetPlan with allocation
    """
    from src.llm import gateway

    # Infer tier: use planning tier if tiering enabled, else default
    if tier is None:
        tier = "planning" if settings_obj.model_tiering_enabled else "default"

    model = gateway.model_for(tier)
    if not model:
        # Fallback to empty model (estimate-only)
        return estimate_plan(settings_obj.memory_context_token_budget)

    return plan_memory_budget(
        model=model,
        token_budget=settings_obj.memory_context_token_budget,
        output_reserve_tokens=settings_obj.memory_context_output_reserve_tokens,
        system_reserve_tokens=settings_obj.memory_context_system_reserve_tokens,
        system_text=system_text,
        shares=(
            settings_obj.memory_context_share_memory,
            settings_obj.memory_context_share_retrieved,
            settings_obj.memory_context_share_history,
        ),
    )


def estimate_plan(token_budget: int) -> MemoryBudgetPlan:
    """
    Estimate-only budget plan (no API calls).

    Used by tests and offline tooling when exact counting is unavailable.

    Args:
        token_budget: Target budget

    Returns:
        MemoryBudgetPlan with estimated allocation (model="", system_counted=False)
    """
    return plan_memory_budget(
        model="",
        token_budget=token_budget,
        output_reserve_tokens=4096,  # default
        system_reserve_tokens=4000,  # default
        system_text="",
        shares=(0.40, 0.40, 0.20),
    )
