"""Tests for PHASE 2 environment-variable-only LLM configuration.

PHASE 2 Requirements:
- All LLM configuration comes from environment variables ONLY
- No YAML config file fallback
- No auto-detection from API key format
- Strict validation: missing required vars raise ValueError
- Models can be different for planning, critique phases
"""

from __future__ import annotations

import pytest

from src.core.config import settings
from src.llm.config import load_llm_config


class TestEnvironmentOnlyConfiguration:
    """Test that all LLM config comes from environment variables."""

    def test_llm_provider_is_required(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Missing LLM_PROVIDER raises ValueError."""
        monkeypatch.setattr(settings, "llm_provider", "")
        monkeypatch.setattr(settings, "llm_model", "claude-3-5-sonnet")
        monkeypatch.setattr(settings, "llm_api_key", "sk-ant-v0-test")

        with pytest.raises(ValueError, match="LLM_PROVIDER environment variable is required"):
            load_llm_config()

    def test_llm_provider_must_be_valid(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Invalid LLM_PROVIDER raises ValueError."""
        monkeypatch.setattr(settings, "llm_provider", "invalid_provider")

        with pytest.raises(ValueError, match="LLM_PROVIDER must be one of"):
            load_llm_config()

    def test_llm_api_key_required_for_anthropic(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Missing LLM_API_KEY for anthropic provider raises ValueError."""
        monkeypatch.setattr(settings, "llm_provider", "anthropic")
        monkeypatch.setattr(settings, "llm_model", "claude-3-5-sonnet")
        monkeypatch.setattr(settings, "llm_api_key", "")

        with pytest.raises(ValueError, match="LLM_API_KEY environment variable is required"):
            load_llm_config()

    def test_llm_api_key_required_for_openai_compatible(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Missing LLM_API_KEY for openai_compatible provider raises ValueError."""
        monkeypatch.setattr(settings, "llm_provider", "openai_compatible")
        monkeypatch.setattr(settings, "llm_model", "gpt-4")
        monkeypatch.setattr(settings, "llm_api_key", "")
        monkeypatch.setattr(settings, "llm_base_url", "")

        # Either api_key or base_url required
        with pytest.raises(ValueError, match="LLM_API_KEY environment variable is required"):
            load_llm_config()

    def test_llm_api_key_not_required_for_claude_cli(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """claude_cli provider doesn't require LLM_API_KEY."""
        monkeypatch.setattr(settings, "llm_provider", "claude_cli")
        monkeypatch.setattr(settings, "llm_model", "claude-3-5-sonnet")
        monkeypatch.setattr(settings, "llm_api_key", "")

        # Should not raise
        config = load_llm_config()
        assert config.provider == "claude_cli"
        assert config.api_key == ""

    def test_llm_model_is_required(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Missing LLM_MODEL raises ValueError."""
        monkeypatch.setattr(settings, "llm_provider", "anthropic")
        monkeypatch.setattr(settings, "llm_model", "")
        monkeypatch.setattr(settings, "llm_api_key", "sk-ant-v0-test")

        with pytest.raises(ValueError, match="LLM_MODEL environment variable is required"):
            load_llm_config()

    def test_planning_model_defaults_to_main_model(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """LLM_PLANNING_MODEL defaults to LLM_MODEL if not set."""
        monkeypatch.setattr(settings, "llm_provider", "anthropic")
        monkeypatch.setattr(settings, "llm_model", "claude-3-5-sonnet")
        monkeypatch.setattr(settings, "llm_api_key", "sk-ant-v0-test")
        monkeypatch.setattr(settings, "llm_planning_model", "")

        config = load_llm_config()
        assert config.models["planning"] == config.models["default"]

    def test_critique_model_defaults_to_main_model(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """LLM_CRITIQUE_MODEL defaults to LLM_MODEL if not set."""
        monkeypatch.setattr(settings, "llm_provider", "anthropic")
        monkeypatch.setattr(settings, "llm_model", "claude-3-5-sonnet")
        monkeypatch.setattr(settings, "llm_api_key", "sk-ant-v0-test")
        monkeypatch.setattr(settings, "llm_critique_model", "")

        config = load_llm_config()
        assert config.models["critique"] == config.models["default"]

    def test_tiered_models_can_differ(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Different models for default, planning, critique are supported."""
        monkeypatch.setattr(settings, "llm_provider", "anthropic")
        monkeypatch.setattr(settings, "llm_model", "claude-3-5-sonnet")
        monkeypatch.setattr(settings, "llm_api_key", "sk-ant-v0-test")
        monkeypatch.setattr(settings, "llm_planning_model", "claude-opus-4-1")
        monkeypatch.setattr(settings, "llm_critique_model", "claude-opus-4-1")

        config = load_llm_config()
        assert config.models["default"] == "claude-3-5-sonnet"
        assert config.models["planning"] == "claude-opus-4-1"
        assert config.models["critique"] == "claude-opus-4-1"

    def test_anthropic_configuration(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Complete Anthropic configuration from env vars."""
        monkeypatch.setattr(settings, "llm_provider", "anthropic")
        monkeypatch.setattr(settings, "llm_model", "claude-3-5-sonnet")
        monkeypatch.setattr(settings, "llm_api_key", "sk-ant-v0-abcdef123")
        monkeypatch.setattr(settings, "llm_base_url", "")

        config = load_llm_config()
        assert config.provider == "anthropic"
        assert config.api_key == "sk-ant-v0-abcdef123"
        assert config.models["default"] == "claude-3-5-sonnet"
        assert config.base_url == ""

    def test_openai_compatible_configuration(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Complete OpenAI-compatible configuration from env vars."""
        monkeypatch.setattr(settings, "llm_provider", "openai_compatible")
        monkeypatch.setattr(settings, "llm_model", "gpt-4")
        monkeypatch.setattr(settings, "llm_api_key", "sk-1234567890")
        monkeypatch.setattr(settings, "llm_base_url", "https://api.openai.com/v1")

        config = load_llm_config()
        assert config.provider == "openai_compatible"
        assert config.api_key == "sk-1234567890"
        assert config.models["default"] == "gpt-4"
        assert config.base_url == "https://api.openai.com/v1"

    def test_groq_configuration(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Groq configuration (as openai_compatible) from env vars."""
        monkeypatch.setattr(settings, "llm_provider", "openai_compatible")
        monkeypatch.setattr(settings, "llm_model", "mixtral-8x7b-32768")
        monkeypatch.setattr(settings, "llm_api_key", "")
        monkeypatch.setattr(settings, "llm_base_url", "https://api.groq.com/openai/v1")

        config = load_llm_config()
        assert config.provider == "openai_compatible"
        assert config.api_key == ""
        assert config.models["default"] == "mixtral-8x7b-32768"
        assert config.base_url == "https://api.groq.com/openai/v1"

    def test_local_ollama_configuration(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Local Ollama server configuration from env vars."""
        monkeypatch.setattr(settings, "llm_provider", "openai_compatible")
        monkeypatch.setattr(settings, "llm_model", "mistral")
        monkeypatch.setattr(settings, "llm_api_key", "")  # No key for local
        monkeypatch.setattr(settings, "llm_base_url", "http://localhost:11434/v1")

        config = load_llm_config()
        assert config.provider == "openai_compatible"
        assert config.api_key == ""
        assert config.models["default"] == "mistral"
        assert config.base_url == "http://localhost:11434/v1"

    def test_no_yaml_fallback(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """YAML config file is NOT used; only env vars."""
        # Set a valid config
        monkeypatch.setattr(settings, "llm_provider", "anthropic")
        monkeypatch.setattr(settings, "llm_model", "claude-3-5-sonnet")
        monkeypatch.setattr(settings, "llm_api_key", "sk-ant-v0-test")

        config = load_llm_config()

        # Verify no YAML sections are present
        # (The options dict should be empty since YAML is not loaded)
        assert isinstance(config.options, dict)
        # No provider-specific options from YAML
        assert len(config.options) == 0

    def test_env_vars_are_stripped_of_whitespace(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Environment variables are stripped of leading/trailing whitespace."""
        monkeypatch.setattr(settings, "llm_provider", "  anthropic  ")
        monkeypatch.setattr(settings, "llm_model", "  claude-3-5-sonnet  ")
        monkeypatch.setattr(settings, "llm_api_key", "  sk-ant-v0-test  ")

        config = load_llm_config()
        assert config.provider == "anthropic"
        assert config.models["default"] == "claude-3-5-sonnet"
        assert config.api_key == "sk-ant-v0-test"
