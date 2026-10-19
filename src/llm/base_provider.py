"""Base provider interface for all LLM providers.

This abstract base class defines the contract that all LLM providers must implement.
Every provider (Anthropic, OpenAI, Groq, etc.) must inherit from this and implement
the required methods.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class BaseLLMProvider(ABC):
    """Abstract base class for all LLM providers.

    Any new provider must:
    1. Inherit from this class
    2. Set the 'name' attribute
    3. Implement is_enabled() method
    4. Implement create_message() method
    """

    name: str = ""  # Provider identifier (e.g., "anthropic", "groq", "openai")

    @abstractmethod
    def is_enabled(self) -> bool:
        """Check if provider is properly configured with API key."""
        pass

    @abstractmethod
    def create_message(self, **kwargs: Any) -> Any:
        """Create a message using this provider's API.

        Args:
            **kwargs: Message parameters (model, messages, temperature, etc.)

        Returns:
            Message response object
        """
        pass
