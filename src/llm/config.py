"""Resolve the model provider settings: environment (Settings) first, then config/model_config.yaml."""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from src.core.config import settings
# from src.llm.key_detector import detect_provider_from_key, detect_model_from_provider  # PHASE 1: Removed, not needed
_CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "model_config.yaml"
# NEW CODE: Extended PROVIDERS tuple to include "groq"
#PROVIDERS = ("anthropic", "claude_cli", "openai_compatible")
PROVIDERS = ("anthropic", "claude_cli", "openai_compatible", "groq")


@dataclass(frozen=True)
class LLMConfig:
    provider: str
    base_url: str
    api_key: str
    models: dict[str, str]  # tier -> model name ("" when not set)
    options: dict[str, Any] = field(default_factory=dict)  # the provider's own section of the YAML file


@lru_cache(maxsize=1)
def _file_config() -> dict[str, Any]:
    try:
        data = yaml.safe_load(_CONFIG_PATH.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    return data if isinstance(data, dict) else {}


def _first(*values: Any) -> str:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return ""


def load_llm_config() -> LLMConfig:
   
    """Load LLM configuration ONLY from environment variables.

    PHASE 2 (ENVIRONMENT-ONLY MODE):
    - No YAML config file fallback
    - No auto-detection from API key format
    - All settings must be explicitly provided via environment variables
    - Strict validation: missing required vars raise ValueError

    Required env vars:
      LLM_PROVIDER: anthropic | claude_cli | openai_compatible | groq
      LLM_MODEL: model name (required)
      LLM_API_KEY: API key (not needed for claude_cli)
      LLM_PLANNING_MODEL: optional, defaults to LLM_MODEL
      LLM_CRITIQUE_MODEL: optional, defaults to LLM_MODEL
      LLM_BASE_URL: optional, for custom endpoints

    COMMENTED OUT (Legacy fallback logic):
    # file_cfg = _file_config()
    # detected_provider = detect_provider_from_key(api_key) if api_key else "anthropic"
    # Models from YAML: file_models.get("default"), file_models.get("planning"), etc.
    # Auto-detection fallback: default_models = detect_model_from_provider(provider)
    """
    #Commented from Latest Code
    #file_cfg = _file_config()
    # provider = _first(getattr(settings, "llm_provider", ""), file_cfg.get("provider"), "anthropic").lower()
    # === ENVIRONMENT-ONLY CONFIGURATION ===

     # === ENVIRONMENT-ONLY CONFIGURATION ===

    # Get provider from environment (required)
    provider = (getattr(settings, "llm_provider", "") or "").strip().lower()
    if not provider:
        raise ValueError(
            "LLM_PROVIDER environment variable is required. "
            f"Must be one of: {', '.join(PROVIDERS)}"
        )

    if provider not in PROVIDERS:
        raise ValueError(
            f"LLM_PROVIDER must be one of {', '.join(PROVIDERS)} (got {provider!r})"
        )

    # Get API key from environment (required for all except claude_cli)
    api_key = (getattr(settings, "llm_api_key", "") or "").strip()
    if provider != "claude_cli" and not api_key:
        raise ValueError(
            f"LLM_API_KEY environment variable is required for provider '{provider}'"
        )

    # Get models from environment (required)
    model_default = (getattr(settings, "llm_model", "") or "").strip()
    if not model_default:
        raise ValueError(
            "LLM_MODEL environment variable is required. "
            "Specify the model name (e.g., claude-3-5-sonnet, gpt-4, llama-2)"
        )

    # Planning and critique models optional; default to main model if not set
    model_planning = (getattr(settings, "llm_planning_model", "") or "").strip() or model_default
    model_critique = (getattr(settings, "llm_critique_model", "") or "").strip() or model_default

    # Get base URL from environment (optional)
    base_url = (getattr(settings, "llm_base_url", "") or "").strip()

    # Commented out: Legacy YAML and auto-detection fallbacks
    # file_cfg = _file_config()
    # file_models = file_cfg.get("models") if isinstance(file_cfg.get("models"), dict) else {}
    # options = file_cfg.get(provider) if isinstance(file_cfg.get(provider), dict) else {}
    # from src.llm.key_detector import detect_provider_from_key, detect_model_from_provider
    # detected_provider = detect_provider_from_key(api_key) if api_key else "anthropic"
    # default_models = detect_model_from_provider(provider)
    # Fallback chain: env -> YAML -> provider defaults
    # No YAML options for now; provider defaults in code will be removed
    # return LLMConfig(
    #     provider=provider,
    #     base_url=_first(getattr(settings, "llm_base_url", ""), file_cfg.get("base_url")),
    #     api_key=_first(getattr(settings, "llm_api_key", "")),
    #     models=models,
    #     options=dict(options),
    # )
    options = {}
    return LLMConfig(
        provider=provider,
        base_url=base_url,
        api_key=api_key,
        models={
            "default": model_default,
            "planning": model_planning,
            "critique": model_critique,
        },
        options=dict(options),
    )
