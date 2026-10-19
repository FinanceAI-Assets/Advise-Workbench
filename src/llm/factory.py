"""Provider factory for dynamic LLM provider instantiation.

This factory enables registration of providers and dynamic instantiation
without hardcoded if-elif chains. Supports easy addition of new providers.
"""

from __future__ import annotations

import logging
from typing import Any

from src.llm.base_provider import BaseLLMProvider

logger = logging.getLogger(__name__)


class ProviderRegistry:
    """Registry for LLM providers using Factory pattern.

    Allows runtime registration and dynamic instantiation of providers
    without hardcoded provider logic.
    """

    _providers: dict[str, type[BaseLLMProvider]] = {}

    @classmethod
    def register(cls, name: str, provider_class: type[BaseLLMProvider]) -> None:
        """Register a provider class.

        Args:
            name: Provider identifier (e.g., "anthropic", "openai", "groq")
            provider_class: Class that inherits from BaseLLMProvider

        Raises:
            ValueError: If provider_class doesn't inherit from BaseLLMProvider
        """
        if not issubclass(provider_class, BaseLLMProvider):
            raise ValueError(
                f"Provider class {provider_class.__name__} must inherit from BaseLLMProvider"
            )
        cls._providers[name] = provider_class
        logger.debug(f"Registered provider: {name} -> {provider_class.__name__}")

    @classmethod
    def create(cls, name: str, config: Any) -> BaseLLMProvider:
        """Create a provider instance.

        Args:
            name: Provider identifier (e.g., "anthropic", "openai", "groq")
            config: Configuration object passed to provider __init__

        Returns:
            Instantiated provider

        Raises:
            ValueError: If provider name not registered
        """
        if name not in cls._providers:
            available = ", ".join(cls._providers.keys())
            raise ValueError(
                f"Unknown provider: {name!r}. Available providers: {available}"
            )
        provider_class = cls._providers[name]
        return provider_class(config)

    @classmethod
    def list_providers(cls) -> list[str]:
        """List all registered provider names."""
        return list(cls._providers.keys())

    @classmethod
    def is_registered(cls, name: str) -> bool:
        """Check if a provider is registered."""
        return name in cls._providers


# Register built-in providers at module load time
def _register_built_in_providers() -> None:
    """Register all built-in providers."""
    try:
        from src.llm.providers.anthropic_api import AnthropicProvider
        ProviderRegistry.register("anthropic", AnthropicProvider)
    except ImportError:
        logger.warning("Could not import AnthropicProvider")

    try:
        from src.llm.providers.claude_cli import ClaudeCliProvider
        ProviderRegistry.register("claude_cli", ClaudeCliProvider)
    except ImportError:
        logger.warning("Could not import ClaudeCliProvider")

    try:
        from src.llm.providers.openai_compatible import OpenAICompatibleProvider
        ProviderRegistry.register("openai_compatible", OpenAICompatibleProvider)
    except ImportError:
        logger.warning("Could not import OpenAICompatibleProvider")

    try:
        from src.llm.providers.groq import GroqProvider
        ProviderRegistry.register("groq", GroqProvider)
    except ImportError:
        logger.warning("Could not import GroqProvider")


# Initialize registry when module loads
_register_built_in_providers()
