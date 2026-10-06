"""Anthropic Messages API through the official SDK."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from src.core.config import settings
from src.llm.capabilities import Capabilities
from src.llm.config import LLMConfig


class AnthropicProvider:
    name = "anthropic"
    capabilities = Capabilities(tools=True, vision=True, thinking=True, anthropic_tools=True)

    def __init__(self, config: LLMConfig) -> None:
        self._config = config

    @property
    def default_models(self) -> dict[str, str]:
        return {
            "default": settings.anthropic_claude_model,
            "planning": str(getattr(settings, "anthropic_planning_model", "") or ""),
            "critique": str(getattr(settings, "anthropic_critique_model", "") or ""),
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
