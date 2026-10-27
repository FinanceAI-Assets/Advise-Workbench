"""Resolve the model provider settings from the environment (.env via ``Settings``) into an ``LLMConfig``.

Switching provider is a one-line change: set ``LLM_PROVIDER`` and keep every provider's own key and model
in .env side by side. Precedence for the primary provider:

  model:    LLM_<TIER>_MODEL -> LLM_MODEL -> <provider>_MODEL (ANTHROPIC_MODEL, OPENAI_MODEL, ...) -> built-in default
  api key:  LLM_API_KEY -> <provider>_API_KEY
  base url: LLM_BASE_URL -> <provider>_BASE_URL -> preset address

The fallback provider (``LLM_FALLBACK_PROVIDER``) ignores the generic LLM_* overrides, which belong to the
primary, and takes its model from ``LLM_FALLBACK_MODEL`` or its own provider settings.
Missing required values raise ``LLMConfigError`` naming the env var to set.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from typing import Any

from src.core.config import settings
from src.llm.errors import LLMConfigError
from src.llm.presets import PRESETS

# Provider implementations. Every preset name (openai, groq, ollama, ...) maps to openai_compatible.
PROVIDERS = ("anthropic", "claude_cli", "openai_compatible", "azure_openai", "bedrock")
SUPPORTED_NAMES = tuple(sorted(set(PROVIDERS) | set(PRESETS)))
TIERS = ("default", "planning", "critique")


@dataclass(frozen=True)
class LLMConfig:
    provider: str  # one of PROVIDERS
    base_url: str
    api_key: str = field(repr=False)
    models: dict[str, str]  # tier -> model name ("" lets the provider choose, e.g. the CLI's default)
    options: dict[str, Any] = field(default_factory=dict, repr=False)  # provider-specific settings
    preset: str = ""  # openai_compatible preset name
    timeout_sec: float = 180.0

    @property
    def fingerprint(self) -> str:
        """Stable digest of every value, so a provider instance is reused until any setting changes."""
        return hashlib.sha256(json.dumps(asdict(self), sort_keys=True, default=str).encode()).hexdigest()

    @property
    def label(self) -> str:
        return f"{self.provider}:{self.preset}" if self.preset and self.preset != self.provider else self.provider


def _s(name: str) -> str:
    return str(getattr(settings, name, "") or "").strip()


def _first(*values: str) -> str:
    return next((v for v in values if v), "")


def resolve_provider_name(name: str) -> tuple[str, str]:
    """``(provider, preset)`` for an LLM_PROVIDER value; raises LLMConfigError for unknown names."""
    key = name.strip().lower()
    if key in PRESETS:
        return "openai_compatible", key
    if key in PROVIDERS:
        return key, ""
    raise LLMConfigError(f"LLM_PROVIDER must be one of {', '.join(SUPPORTED_NAMES)} (got {name!r})")


def _require(missing: list[str], provider: str) -> None:
    if missing:
        raise LLMConfigError(f"LLM_PROVIDER={provider} needs {' and '.join(missing)} in .env")


def load_llm_config(provider: str | None = None) -> LLMConfig:
    """Config for ``LLM_PROVIDER``, or for ``provider`` when building the fallback."""
    primary = provider is None
    raw = _s("llm_provider") if primary else provider.strip()
    if not raw:
        raise LLMConfigError(f"LLM_PROVIDER is required in .env. Use one of: {', '.join(SUPPORTED_NAMES)}")
    kind, preset = resolve_provider_name(raw)

    def generic(name: str) -> str:  # LLM_* overrides apply to the primary provider only
        return _s(name) if primary else ""

    override_model = generic("llm_model") or ("" if primary else _s("llm_fallback_model"))
    api_key = generic("llm_api_key")
    base_url = generic("llm_base_url")
    options: dict[str, Any] = {}
    missing: list[str] = []
    label = preset or kind

    if kind == "anthropic":
        api_key = _first(api_key, _s("anthropic_api_key"))
        default_model = _first(override_model, _s("anthropic_model"), _s("anthropic_claude_model"))
        if not api_key:
            missing.append("ANTHROPIC_API_KEY (or LLM_API_KEY)")
    elif kind == "claude_cli":
        api_key = ""  # the CLI uses its own sign-in; API credentials are never passed to it
        default_model = _first(override_model, _s("claude_cli_model"))
        options = {
            "path": _s("claude_cli_path") or "claude",
            "timeout_sec": float(getattr(settings, "claude_cli_timeout_sec", 600) or 600),
            "tools_enabled": bool(getattr(settings, "claude_cli_tools_enabled", True)),
        }
    elif kind == "bedrock":
        default_model = _first(override_model, _s("bedrock_model"))
        options = {
            "aws_region": _s("aws_region"),
            "aws_profile": _s("aws_profile"),
            "aws_access_key": _s("aws_access_key_id"),
            "aws_secret_key": _s("aws_secret_access_key"),
            "aws_session_token": _s("aws_session_token"),
            "anthropic_tools": bool(getattr(settings, "bedrock_anthropic_tools_enabled", False)),
        }
        if not options["aws_region"]:
            missing.append("AWS_REGION")
        if not default_model:
            missing.append("BEDROCK_MODEL (or LLM_MODEL)")
    else:  # openai_compatible / azure_openai share the chat-completions options
        options = {
            "supports_tools": bool(getattr(settings, "openai_compat_supports_tools", True)),
            "supports_vision": bool(getattr(settings, "openai_compat_supports_vision", True)),
            "max_tokens_param": _s("openai_compat_max_tokens_param") or "auto",
        }
        if kind == "azure_openai":
            api_key = _first(api_key, _s("azure_openai_api_key"))
            base_url = _first(base_url, _s("azure_openai_endpoint")).rstrip("/")
            default_model = _first(override_model, _s("azure_openai_deployment"))
            options["api_version"] = _s("azure_openai_api_version")
            options["reasoning_model_prefixes"] = PRESETS["openai"].reasoning_model_prefixes
            options["stream_usage"] = True
            missing += [
                v
                for v, ok in (
                    ("AZURE_OPENAI_ENDPOINT", base_url),
                    ("AZURE_OPENAI_API_KEY", api_key),
                    ("AZURE_OPENAI_DEPLOYMENT (or LLM_MODEL)", default_model),
                )
                if not ok
            ]
        else:
            spec = PRESETS[preset]
            preset_key = _s(spec.key_setting) if spec.key_setting else ""
            api_key = _first(api_key, preset_key)
            preset_base = _s("openai_base_url") if preset == "openai" else ""
            base_url = _first(base_url, preset_base, spec.base_url)
            default_model = _first(override_model, _s(spec.model_setting) if spec.model_setting else "")
            options.update(
                stream_usage=spec.stream_usage,
                reasoning_model_prefixes=spec.reasoning_model_prefixes,
                extra_headers=dict(spec.extra_headers),
            )
            if not base_url:
                missing.append("LLM_BASE_URL")
            if spec.key_setting and not spec.key_optional and not api_key:
                missing.append(f"{spec.key_setting.upper()} (or LLM_API_KEY)")
            if not default_model:
                hint = f"{spec.model_setting.upper()} or LLM_MODEL" if spec.model_setting else "LLM_MODEL"
                missing.append(hint)

    _require(missing, label)
    models = {"default": default_model}
    for tier in TIERS[1:]:
        models[tier] = generic(f"llm_{tier}_model") or default_model
    return LLMConfig(
        provider=kind,
        base_url=base_url,
        api_key=api_key,
        models=models,
        options=options,
        preset=preset,
        timeout_sec=float(getattr(settings, "llm_timeout_sec", 180) or 180),
    )


def load_fallback_config() -> LLMConfig | None:
    """Config for ``LLM_FALLBACK_PROVIDER``, or None when no fallback is set."""
    name = _s("llm_fallback_provider")
    return load_llm_config(name) if name else None
