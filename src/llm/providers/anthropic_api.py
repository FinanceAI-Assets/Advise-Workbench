"""Anthropic Messages API through the official SDK."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from src.core.config import settings
# ORIGINAL CODE (commented):
# from src.llm.capabilities import Capabilities
# from src.llm.config import LLMConfig
#
#
# class AnthropicProvider:
#     name = "anthropic"
#     capabilities = Capabilities(tools=True, vision=True, thinking=True, anthropic_tools=True)

# NEW CODE (inherit from BaseLLMProvider for factory pattern support):
from src.llm.base_provider import BaseLLMProvider
from src.llm.capabilities import Capabilities
from src.llm.config import LLMConfig


class AnthropicProvider(BaseLLMProvider):
    name = "anthropic"
    capabilities = Capabilities(tools=True, vision=True, thinking=True, anthropic_tools=True)

    def __init__(self, config: LLMConfig) -> None:
        self._config = config

    @property
    def default_models(self) -> dict[str, str]:
        """
        PHASE 2 (ENVIRONMENT-ONLY):
        Models come from LLMConfig.models, which are populated from environment variables only.
        No fallback to settings or hardcoded defaults.

        Commented out (Legacy):
        # return {
        #     "default": settings.anthropic_claude_model,
        #     "planning": str(getattr(settings, "anthropic_planning_model", "") or ""),
        #     "critique": str(getattr(settings, "anthropic_critique_model", "") or ""),
        # }
        """
        return {
           "default": self._config.models.get("default", ""),
            "planning": self._config.models.get("planning", ""),
            "critique": self._config.models.get("critique", ""),
        }

    def _api_key(self) -> str:
        return (self._config.api_key or settings.anthropic_api_key or "").strip()

    def is_enabled(self) -> bool:
        return bool(self._api_key())

    def create_message(
        self,
        *,
        stream: bool = False,
        beta: bool = False,
        on_event: Callable[[], None] | None = None,
        **kwargs: Any,
    ) -> Any:
        # Lazy import so unit tests can run without the dependency installed/configured.
        from anthropic import Anthropic  # type: ignore

        client_kwargs: dict[str, Any] = {"api_key": self._api_key()}
        if self._config.base_url:
            client_kwargs["base_url"] = self._config.base_url
        client = Anthropic(**client_kwargs)
        if stream:
            with client.messages.stream(**kwargs) as response:
                for _ in response:
                    if on_event:
                        on_event()
                return response.get_final_message()
        api = client.beta.messages if beta else client.messages
        return api.create(**kwargs)
