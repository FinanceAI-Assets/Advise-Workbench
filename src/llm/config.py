"""Resolve the model provider settings: environment (Settings) first, then config/model_config.yaml."""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from src.core.config import settings

_CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "model_config.yaml"
PROVIDERS = ("anthropic", "claude_cli", "openai_compatible")


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
    file_cfg = _file_config()
    provider = _first(getattr(settings, "llm_provider", ""), file_cfg.get("provider"), "anthropic").lower()
    if provider not in PROVIDERS:
        raise ValueError(f"LLM_PROVIDER must be one of {', '.join(PROVIDERS)} (got {provider!r})")
    file_models = file_cfg.get("models") if isinstance(file_cfg.get("models"), dict) else {}
    models = {
        "default": _first(getattr(settings, "llm_model", ""), file_models.get("default")),
        "planning": _first(getattr(settings, "llm_planning_model", ""), file_models.get("planning")),
        "critique": _first(getattr(settings, "llm_critique_model", ""), file_models.get("critique")),
    }
    options = file_cfg.get(provider) if isinstance(file_cfg.get(provider), dict) else {}
    return LLMConfig(
        provider=provider,
        base_url=_first(getattr(settings, "llm_base_url", ""), file_cfg.get("base_url")),
        api_key=_first(getattr(settings, "llm_api_key", "")),
        models=models,
        options=dict(options),
    )
