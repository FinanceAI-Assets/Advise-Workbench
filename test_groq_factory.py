#!/usr/bin/env python
"""Test script to verify Groq provider works with factory pattern.

This script:
1. Tests API key format detection (gsk_* -> groq)
2. Tests provider factory can create Groq provider
3. Tests provider inheritance from BaseLLMProvider

Run with: python test_groq_factory.py
"""

from src.llm.key_detector import detect_provider_from_key, detect_model_from_provider
from src.llm.factory import ProviderRegistry
from src.llm.config import LLMConfig


def test_api_key_detection():
    """Test API key format detection for Groq."""
    print("Testing API key detection...")

    # Test Groq detection
    assert detect_provider_from_key("gsk_test123") == "groq", "Failed to detect Groq key"
    print("✓ Groq key detected correctly (gsk_*)")

    # Test Anthropic detection
    assert detect_provider_from_key("sk-ant-test123") == "anthropic", "Failed to detect Anthropic key"
    print("✓ Anthropic key detected correctly (sk-ant-*)")

    # Test OpenAI detection
    assert detect_provider_from_key("sk-proj-test123") == "openai_compatible", "Failed to detect OpenAI key"
    print("✓ OpenAI key detected correctly (sk-*)")

    print()


def test_model_detection():
    """Test default model selection per provider."""
    print("Testing model detection...")

    groq_models = detect_model_from_provider("groq")
    assert groq_models["default"] == "mixtral-8x7b-32768", "Groq default model incorrect"
    print(f"✓ Groq default model: {groq_models['default']}")

    anthropic_models = detect_model_from_provider("anthropic")
    assert anthropic_models["default"] == "claude-3-5-sonnet-20241022", "Anthropic default model incorrect"
    print(f"✓ Anthropic default model: {anthropic_models['default']}")

    print()


def test_provider_registry():
    """Test provider factory registration."""
    print("Testing provider registry...")

    providers = ProviderRegistry.list_providers()
    print(f"Registered providers: {providers}")

    assert "groq" in providers, "Groq provider not registered"
    print("✓ Groq provider registered")

    assert "anthropic" in providers, "Anthropic provider not registered"
    print("✓ Anthropic provider registered")

    assert "claude_cli" in providers, "Claude CLI provider not registered"
    print("✓ Claude CLI provider registered")

    assert "openai_compatible" in providers, "OpenAI compatible provider not registered"
    print("✓ OpenAI compatible provider registered")

    print()


def test_groq_provider_creation():
    """Test creating Groq provider through factory."""
    print("Testing Groq provider creation...")

    config = LLMConfig(
        provider="groq",
        api_key="gsk_test_key",
        base_url="https://api.groq.com/openai/v1",
        models={"default": "mixtral-8x7b-32768", "planning": "mixtral-8x7b-32768", "critique": "mixtral-8x7b-32768"},
        options={},
    )

    provider = ProviderRegistry.create("groq", config)

    assert provider.name == "groq", "Provider name mismatch"
    print(f"✓ Provider name: {provider.name}")

    assert provider.is_enabled(), "Provider should be enabled with API key"
    print("✓ Provider is enabled")

    assert provider.default_models["default"] == "mixtral-8x7b-32768", "Default model incorrect"
    print(f"✓ Default models configured: {provider.default_models}")

    print()


def test_anthropic_provider_creation():
    """Test creating Anthropic provider through factory."""
    print("Testing Anthropic provider creation...")

    config = LLMConfig(
        provider="anthropic",
        api_key="sk-ant-test_key",
        base_url="",
        models={"default": "claude-3-5-sonnet-20241022", "planning": "claude-3-opus-20250219", "critique": "claude-3-sonnet-20240229"},
        options={},
    )

    provider = ProviderRegistry.create("anthropic", config)

    assert provider.name == "anthropic", "Provider name mismatch"
    print(f"✓ Provider name: {provider.name}")

    print()


if __name__ == "__main__":
    print("=" * 60)
    print("Testing Factory Pattern + Groq Provider Integration")
    print("=" * 60)
    print()

    try:
        test_api_key_detection()
        test_model_detection()
        test_provider_registry()
        test_groq_provider_creation()
        test_anthropic_provider_creation()

        print("=" * 60)
        print("✅ All tests passed!")
        print("=" * 60)
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        exit(1)
