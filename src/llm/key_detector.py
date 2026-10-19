"""API key format detection for automatic provider selection.

Detects which provider to use based on API key format/prefix.
Enables zero-configuration provider switching: just change the API key.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def detect_provider_from_key(api_key: str) -> str:
    """Detect which provider to use based on API key format.

    Args:
        api_key: The API key to analyze

    Returns:
        Provider name (e.g., "anthropic", "openai", "groq")

    Examples:
   
    """
    if not api_key:
        return "anthropic"  # Default

    api_key_lower = api_key.lower()

    # Anthropic keys start with "sk-ant-"
    if api_key.startswith("sk-ant-"):
        return "anthropic"

    # Groq keys start with ""
    if api_key.startswith("gsk_"):
        return "groq"

    # OpenAI keys start with "sk-" (but not "sk-ant-")
    # Can be: sk-proj-*, sk-*
    if api_key.startswith("sk-"):
        return "openai_compatible"

    # Google Gemini keys start with "AIza"
    if api_key.startswith("AIza"):
        return "gemini"

    # Cohere keys start with "co_"
    if api_key.startswith("co_"):
        return "cohere"

    # Mistral keys start with "mk-"
    if api_key.startswith("mk-"):
        return "mistral"

    # Default to openai_compatible if format unknown
    # (most general format, can work with many APIs)
    logger.debug(f"Unknown API key format, defaulting to openai_compatible")
    return "openai_compatible"


def detect_model_from_provider(provider: str) -> dict[str, str]:
    """Get default models for a provider.

    Args:
        provider: Provider name (e.g., "anthropic", "openai", "groq")

    Returns:
        Dictionary with keys "default", "planning", "critique"
        Each maps to the recommended model name for that use case
    """
    models_by_provider = {
        "anthropic": {
            "default": "claude-3-5-sonnet-20241022",
            "planning": "claude-3-opus-20250219",
            "critique": "claude-3-sonnet-20240229",
        },
        "groq": {
            "default": "allam-2-7b",
            "planning": "allam-2-7b",
            "critique": "allam-2-7b",
        },
        "openai_compatible": {
            "default": "gpt-4-turbo",
            "planning": "gpt-4-turbo",
            "critique": "gpt-4-turbo",
        },
        "gemini": {
            "default": "gemini-2.0-pro",
            "planning": "gemini-2.0-pro",
            "critique": "gemini-1.5-pro",
        },
        "cohere": {
            "default": "command-r-plus",
            "planning": "command-r-plus",
            "critique": "command-r-plus",
        },
        "mistral": {
            "default": "mistral-large",
            "planning": "mistral-large",
            "critique": "mistral-large",
        },
    }

    return models_by_provider.get(provider, models_by_provider["openai_compatible"])
