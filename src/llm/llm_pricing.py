"""LLM token cost calculation based on per-MTok pricing."""
from __future__ import annotations

import json
import logging

from src.core.config import settings

logger = logging.getLogger(__name__)

# Workstream F: Standard model pricing ($/MTok) for Anthropic models
DEFAULT_MODEL_PRICES = {
    "claude-opus-4-8": {"input": 3.00, "output": 15.00},
    "claude-opus-4-1": {"input": 3.00, "output": 15.00},
    "claude-sonnet-4-6": {"input": 3.00, "output": 15.00},
    "claude-sonnet-4-5": {"input": 3.00, "output": 15.00},
    "claude-haiku-4-5": {"input": 1.00, "output": 5.00},
    "claude-haiku-3-5": {"input": 0.80, "output": 4.00},
}


def get_model_pricing(model: str) -> tuple[float, float]:
    """
    Get input and output pricing for a model.

    Workstream F: reads per-model prices from llm_model_prices_json setting,
    falls back to DEFAULT_MODEL_PRICES, then to global settings.

    Returns: (input_price_per_mtok, output_price_per_mtok)
    """
    # Try to parse model prices from settings
    try:
        model_prices_json = getattr(settings, "llm_model_prices_json", "")
        if model_prices_json:
            model_prices = json.loads(model_prices_json)
            if model in model_prices:
                prices = model_prices[model]
                return float(prices.get("input", prices[0])), float(prices.get("output", prices[1]))
    except (json.JSONDecodeError, (KeyError, TypeError, IndexError)):
        logger.info(f"Failed to parse llm_model_prices_json, using defaults")

    # Try default model prices
    if model in DEFAULT_MODEL_PRICES:
        p = DEFAULT_MODEL_PRICES[model]
        return p["input"], p["output"]

    # Fall back to global settings
    p_in = getattr(settings, "llm_price_input_per_mtok", 3.00)
    p_out = getattr(settings, "llm_price_output_per_mtok", 15.00)
    return float(p_in), float(p_out)


def calculate_run_cost_usd(
    *,
    input_tokens: int,
    output_tokens: int,
    cache_read_tokens: int = 0,
    cache_creation_tokens: int = 0,
    model: str = "",
) -> float:
    """
    Calculate LLM run cost in USD.

    Workstream F: uses model-specific pricing when model is provided.
    Old code (kept for reference):
    # p_in = getattr(settings, "llm_price_input_per_mtok", 3.00)
    # p_out = getattr(settings, "llm_price_output_per_mtok", 15.00)
    """
    # Workstream F: get model-specific pricing if model provided
    if model:
        p_in, p_out = get_model_pricing(model)
    else:
        p_in = getattr(settings, "llm_price_input_per_mtok", 3.00)
        p_out = getattr(settings, "llm_price_output_per_mtok", 15.00)

    p_cr = getattr(settings, "llm_price_cache_read_per_mtok", 0.30)
    p_cc = getattr(settings, "llm_price_cache_creation_per_mtok", 3.75)
    return round(
        input_tokens * p_in / 1_000_000
        + output_tokens * p_out / 1_000_000
        + cache_read_tokens * p_cr / 1_000_000
        + cache_creation_tokens * p_cc / 1_000_000,
        6,
    )
