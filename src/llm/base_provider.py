"""Contract every LLM provider implements.

``create_message`` takes Anthropic Messages API arguments (model, system, messages, max_tokens, temperature,
tools, ...) and returns a message with ``content`` blocks, ``stop_reason`` and ``usage``, so callers treat
every provider the same way. Providers raise ``src.llm.errors`` types, never their SDK's own exceptions.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, ClassVar

from src.llm.capabilities import Capabilities
from src.llm.config import LLMConfig


@dataclass(frozen=True)
class HealthStatus:
    ok: bool
    detail: str = ""
    info: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ToolCallRecord:
    """One tool call made during a delegated tool session (see ``BaseLLMProvider.run_tool_session``)."""

    tool_use_id: str
    name: str
    input: dict[str, Any]
    output: str
    is_error: bool


# executor(name, input) -> (output text, is_error); runs the app's own tool implementation.
ToolExecutor = Callable[[str, dict[str, Any]], tuple[str, bool]]
# on_round(round number, the calls made in that round)
RoundCallback = Callable[[int, list[ToolCallRecord]], None]


class BaseLLMProvider(ABC):
    """Subclasses set ``name`` and ``capabilities`` and implement ``is_enabled`` and ``create_message``.

    Instances are cached by the factory and shared across threads, so anything they hold (SDK clients,
    HTTP pools) must be thread-safe. ``close`` releases those resources when the config changes.
    """

    name: ClassVar[str] = ""
    capabilities: Capabilities = Capabilities()

    def __init__(self, config: LLMConfig) -> None:
        self._config = config

    @property
    def config(self) -> LLMConfig:
        return self._config

    @property
    def default_models(self) -> dict[str, str]:
        return dict(self._config.models)

    @abstractmethod
    def is_enabled(self) -> bool:
        """True when the provider can be called (credentials present, CLI installed, ...). Never raises."""

    @abstractmethod
    def create_message(
        self,
        *,
        stream: bool = False,
        beta: bool = False,
        on_event: Callable[[], None] | None = None,
        **kwargs: Any,
    ) -> Any:
        """One model call. ``on_event`` is called periodically so the caller can abort (it may raise)."""

    def health_check(self) -> HealthStatus:
        """Cheap readiness check that spends no tokens."""
        enabled = self.is_enabled()
        return HealthStatus(ok=enabled, detail="configured" if enabled else "not configured")

    def run_tool_session(
        self,
        *,
        system: Any,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        executor: ToolExecutor,
        max_rounds: int,
        model: str = "",
        on_round: RoundCallback | None = None,
        on_event: Callable[[], None] | None = None,
    ) -> Any:
        """Run a whole tool loop inside the provider (only when ``capabilities.delegated_tools``).

        Returns a message (as ``create_message`` does) whose text is the final answer and whose
        ``usage`` covers the whole session; each round's calls are reported through ``on_round``.
        """
        raise NotImplementedError(f"{self.name} does not run tool sessions itself")

    def close(self) -> None:  # noqa: B027 — optional hook; providers without clients have nothing to release
        """Release clients and connection pools."""
