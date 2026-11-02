"""Anthropic Messages API through the official SDK. The full feature set: tools, vision, thinking, bash/text-editor."""

from __future__ import annotations

import threading
from collections.abc import Callable
from typing import Any

from src.llm.base_provider import BaseLLMProvider, HealthStatus
from src.llm.capabilities import Capabilities
from src.llm.config import LLMConfig
from src.llm.errors import LLMError, LLMTimeoutError, LLMUnavailableError, parse_retry_after, status_error


def map_anthropic_error(exc: Exception, provider: str) -> Exception:
    """Translate an ``anthropic`` SDK exception (also raised by AnthropicBedrock) into an LLMError."""
    import anthropic

    if isinstance(exc, anthropic.APITimeoutError):
        return LLMTimeoutError(str(exc), provider=provider)
    if isinstance(exc, anthropic.APIConnectionError):
        return LLMUnavailableError(str(exc), provider=provider)
    if isinstance(exc, anthropic.APIStatusError):
        retry_after = parse_retry_after(exc.response.headers.get("retry-after")) if exc.response is not None else None
        return status_error(exc.status_code, str(exc), provider=provider, retry_after=retry_after)
    return exc


class AnthropicProvider(BaseLLMProvider):
    name = "anthropic"
    capabilities = Capabilities(tools=True, vision=True, thinking=True, anthropic_tools=True)

    def __init__(self, config: LLMConfig) -> None:
        super().__init__(config)
        self._client: Any = None
        self._client_lock = threading.Lock()

    def is_enabled(self) -> bool:
        return bool(self._config.api_key)

    def _new_client(self) -> Any:
        import anthropic  # resolved at call time so tests can patch anthropic.Anthropic

        kwargs: dict[str, Any] = {"api_key": self._config.api_key, "timeout": self._config.timeout_sec, "max_retries": 0}
        if self._config.base_url:
            kwargs["base_url"] = self._config.base_url
        return anthropic.Anthropic(**kwargs)

    @property
    def client(self) -> Any:
        """One SDK client per provider instance: it is thread-safe and keeps its HTTP connections warm."""
        if self._client is None:
            with self._client_lock:
                if self._client is None:
                    self._client = self._new_client()
        return self._client

    def create_message(
        self,
        *,
        stream: bool = False,
        beta: bool = False,
        on_event: Callable[[], None] | None = None,
        **kwargs: Any,
    ) -> Any:
        try:
            if stream:
                api = self.client.beta.messages if beta else self.client.messages
                with api.stream(**kwargs) as response:
                    for _ in response:
                        if on_event:
                            on_event()
                    return response.get_final_message()
            api = self.client.beta.messages if beta else self.client.messages
            return api.create(**kwargs)
        except LLMError:
            raise
        except Exception as exc:  # noqa: BLE001 — anything else is mapped or re-raised unchanged
            mapped = map_anthropic_error(exc, self._config.label)
            if mapped is exc:
                raise
            raise mapped from exc

    def health_check(self) -> HealthStatus:
        if not self.is_enabled():
            return HealthStatus(ok=False, detail="ANTHROPIC_API_KEY (or LLM_API_KEY) is not set")
        return HealthStatus(ok=True, detail="configured")

    def close(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None
