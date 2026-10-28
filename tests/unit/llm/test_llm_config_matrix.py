"""LLM_PROVIDER resolution: every provider and preset, precedence rules and actionable errors."""

from __future__ import annotations

import pytest

from src.core.config import settings
from src.llm.config import SUPPORTED_NAMES, load_fallback_config, load_llm_config
from src.llm.errors import LLMConfigError

_ALL_FIELDS = (
    "llm_provider", "llm_base_url", "llm_api_key", "llm_model", "llm_planning_model", "llm_critique_model",
    "llm_fallback_provider", "llm_fallback_model", "anthropic_api_key", "anthropic_model", "claude_cli_model",
    "openai_api_key", "openai_base_url", "openai_model", "groq_api_key", "openrouter_api_key", "litellm_api_key",
    "azure_openai_endpoint", "azure_openai_api_key", "azure_openai_deployment",
    "aws_region", "aws_profile", "aws_access_key_id", "aws_secret_access_key", "aws_session_token", "bedrock_model",
)


@pytest.fixture(autouse=True)
def blank_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in _ALL_FIELDS:
        monkeypatch.setattr(settings, name, "")


def _set(monkeypatch: pytest.MonkeyPatch, **values: str) -> None:
    for name, value in values.items():
        monkeypatch.setattr(settings, name, value)


def test_provider_is_required_and_validated(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(LLMConfigError, match="LLM_PROVIDER is required"):
        load_llm_config()
    _set(monkeypatch, llm_provider="nope")
    with pytest.raises(LLMConfigError, match="LLM_PROVIDER must be one of"):
        load_llm_config()


def test_supported_names_cover_all_providers_and_presets() -> None:
    for name in ("anthropic", "claude_cli", "openai", "openai_compatible", "azure_openai", "bedrock", "groq", "ollama", "openrouter"):
        assert name in SUPPORTED_NAMES


def test_switching_is_one_line_when_all_keys_are_in_env(monkeypatch: pytest.MonkeyPatch) -> None:
    _set(
        monkeypatch,
        anthropic_api_key="sk-ant", anthropic_model="claude-sonnet-4-6",
        openai_api_key="sk-oai", openai_model="gpt-4.1",
        azure_openai_endpoint="https://res.openai.azure.com/", azure_openai_api_key="az", azure_openai_deployment="gpt4o-prod",
        aws_region="us-east-1", bedrock_model="us.anthropic.claude-sonnet-4-5-v1:0",
        claude_cli_model="sonnet",
    )
    expected = {
        "anthropic": ("anthropic", "claude-sonnet-4-6", "sk-ant"),
        "openai": ("openai_compatible", "gpt-4.1", "sk-oai"),
        "azure_openai": ("azure_openai", "gpt4o-prod", "az"),
        "bedrock": ("bedrock", "us.anthropic.claude-sonnet-4-5-v1:0", ""),
        "claude_cli": ("claude_cli", "sonnet", ""),
    }
    for name, (provider, model, key) in expected.items():
        _set(monkeypatch, llm_provider=name)
        config = load_llm_config()
        assert (config.provider, config.models["default"], config.api_key) == (provider, model, key), name


def test_generic_overrides_win(monkeypatch: pytest.MonkeyPatch) -> None:
    _set(
        monkeypatch,
        llm_provider="openai", openai_api_key="sk-oai", openai_model="gpt-4.1",
        llm_api_key="sk-override", llm_model="gpt-4.1-mini", llm_planning_model="o3", llm_base_url="https://proxy.local/v1",
    )
    config = load_llm_config()
    assert config.api_key == "sk-override"
    assert config.base_url == "https://proxy.local/v1"
    assert config.models == {"default": "gpt-4.1-mini", "planning": "o3", "critique": "gpt-4.1-mini"}


def test_presets_fill_base_url_and_key(monkeypatch: pytest.MonkeyPatch) -> None:
    _set(monkeypatch, llm_provider="groq", groq_api_key="gsk", llm_model="llama-3.3-70b")
    config = load_llm_config()
    assert (config.provider, config.preset, config.base_url, config.api_key) == (
        "openai_compatible", "groq", "https://api.groq.com/openai/v1", "gsk",
    )
    assert config.label == "openai_compatible:groq"


def test_local_presets_need_no_key(monkeypatch: pytest.MonkeyPatch) -> None:
    _set(monkeypatch, llm_provider="ollama", llm_model="llama3.1")
    assert load_llm_config().base_url == "http://localhost:11434/v1"
    _set(monkeypatch, llm_provider="litellm")
    assert load_llm_config().api_key == ""


def test_generic_compatible_never_borrows_provider_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    _set(monkeypatch, llm_provider="openai_compatible", openai_api_key="sk-oai", llm_model="m")
    with pytest.raises(LLMConfigError, match="LLM_BASE_URL"):
        load_llm_config()
    _set(monkeypatch, llm_base_url="http://gateway.internal/v1")
    assert load_llm_config().api_key == ""


@pytest.mark.parametrize(
    ("provider", "message"),
    [
        ("anthropic", "ANTHROPIC_API_KEY"),
        ("openai", "OPENAI_API_KEY"),
        ("groq", "GROQ_API_KEY"),
        ("azure_openai", "AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_API_KEY and AZURE_OPENAI_DEPLOYMENT"),
        ("bedrock", "AWS_REGION and BEDROCK_MODEL"),
    ],
)
def test_missing_values_name_the_env_var(monkeypatch: pytest.MonkeyPatch, provider: str, message: str) -> None:
    _set(monkeypatch, llm_provider=provider)
    with pytest.raises(LLMConfigError, match=message):
        load_llm_config()


def test_claude_cli_needs_nothing_and_never_gets_api_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    _set(monkeypatch, llm_provider="claude_cli", llm_api_key="sk-should-not-pass", anthropic_api_key="sk-ant")
    config = load_llm_config()
    assert config.api_key == ""
    assert config.models["default"] == ""  # the CLI picks its own default model
    assert config.options["tools_enabled"] is True


def test_fallback_ignores_primary_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    _set(
        monkeypatch,
        llm_provider="claude_cli", llm_model="haiku", llm_api_key="primary-only",
        llm_fallback_provider="anthropic", anthropic_api_key="sk-ant", llm_fallback_model="claude-sonnet-4-6",
    )
    fallback = load_fallback_config()
    assert fallback is not None
    assert fallback.provider == "anthropic"
    assert fallback.api_key == "sk-ant"
    assert fallback.models["default"] == "claude-sonnet-4-6"
    _set(monkeypatch, llm_fallback_provider="")
    assert load_fallback_config() is None


def test_secrets_stay_out_of_repr(monkeypatch: pytest.MonkeyPatch) -> None:
    _set(monkeypatch, llm_provider="bedrock", aws_region="eu-west-1", bedrock_model="m", aws_secret_access_key="TOPSECRET")
    assert "TOPSECRET" not in repr(load_llm_config())


def test_fingerprint_changes_with_any_setting(monkeypatch: pytest.MonkeyPatch) -> None:
    _set(monkeypatch, llm_provider="anthropic", anthropic_api_key="a")
    first = load_llm_config().fingerprint
    assert load_llm_config().fingerprint == first
    _set(monkeypatch, anthropic_api_key="b")
    assert load_llm_config().fingerprint != first
