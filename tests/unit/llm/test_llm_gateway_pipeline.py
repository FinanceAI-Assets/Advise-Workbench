"""Gateway pipeline: provider caching, retries, circuit breaker, fallback and single usage charge."""

from __future__ import annotations

from typing import Any

import pytest

from src.core.config import settings
from src.core.exceptions import RunBudgetExceeded
from src.llm import gateway
from src.llm.base_provider import BaseLLMProvider
from src.llm.capabilities import Capabilities
from src.llm.config import LLMConfig
from src.llm.errors import LLMAuthError, LLMBadRequestError, LLMConfigError, LLMRateLimitError, LLMUnavailableError
from src.llm.factory import ProviderRegistry
from src.llm.middleware import resilience
from src.llm.providers._common import message
from src.llm.run_budget import run_llm_budget


class ScriptedProvider(BaseLLMProvider):
    """Raises or returns whatever ``script`` holds, in order; records every call."""

    name = "scripted"
    script: list[Any] = []
    calls: list[dict[str, Any]] = []
    capabilities = Capabilities(tools=True, vision=True, thinking=False)

    def is_enabled(self) -> bool:
        return True

    def create_message(self, *, stream=False, beta=False, on_event=None, **kwargs):
        type(self).calls.append({"provider": self.config.provider, **kwargs})
        outcome = type(self).script.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def _reply(text: str = "ok", tokens: tuple[int, int] = (10, 5)) -> Any:
    return message(content=[{"type": "text", "text": text}], stop_reason="end_turn", input_tokens=tokens[0], output_tokens=tokens[1], model="m")


@pytest.fixture
def scripted(monkeypatch: pytest.MonkeyPatch) -> type[ScriptedProvider]:
    ScriptedProvider.script = []
    ScriptedProvider.calls = []
    monkeypatch.setitem(ProviderRegistry._providers, "anthropic", ScriptedProvider)
    monkeypatch.setattr(settings, "llm_provider", "anthropic")
    monkeypatch.setattr(settings, "anthropic_api_key", "k")
    monkeypatch.setattr(settings, "llm_api_key", "")
    monkeypatch.setattr(settings, "llm_model", "")
    monkeypatch.setattr(resilience, "_wait", lambda delay, on_event: None)
    return ScriptedProvider


def _call() -> Any:
    return gateway.create_message(model="m", max_tokens=10, messages=[{"role": "user", "content": "hi"}])


def test_provider_instance_is_cached_until_settings_change(scripted, monkeypatch: pytest.MonkeyPatch) -> None:
    first = gateway.get_provider()
    assert gateway.get_provider() is first
    monkeypatch.setattr(settings, "anthropic_api_key", "other")
    assert gateway.get_provider() is not first


def test_retryable_errors_are_retried(scripted, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "llm_max_retries", 2)
    scripted.script = [LLMRateLimitError("slow down", retry_after=0), LLMUnavailableError("503"), _reply("third time")]
    assert _call().content[0]["text"] == "third time"
    assert len(scripted.calls) == 3


@pytest.mark.parametrize("error", [LLMBadRequestError("bad"), LLMAuthError("no")])
def test_non_retryable_errors_surface_immediately(scripted, monkeypatch: pytest.MonkeyPatch, error) -> None:
    monkeypatch.setattr(settings, "llm_max_retries", 3)
    scripted.script = [error, _reply()]
    with pytest.raises(type(error)):
        _call()
    assert len(scripted.calls) == 1


def test_retry_after_hint_is_honoured() -> None:
    assert resilience.backoff_delay(0, 7.0) == 7.0
    assert resilience.backoff_delay(0, 999.0) == 60.0
    assert 0.5 <= resilience.backoff_delay(0, None) <= 1.0


def test_retry_wait_polls_for_abort() -> None:
    class Aborted(Exception):
        pass

    def abort() -> None:
        raise Aborted

    with pytest.raises(Aborted):
        resilience._wait(5.0, abort)


def test_circuit_breaker_opens_then_recovers(scripted, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "llm_circuit_breaker_failures", 2)
    monkeypatch.setattr(settings, "llm_circuit_breaker_reset_sec", 30)
    scripted.script = [LLMUnavailableError("down"), LLMUnavailableError("down")]
    for _ in range(2):
        with pytest.raises(LLMUnavailableError):
            _call()
    with pytest.raises(LLMUnavailableError, match="circuit breaker open"):
        _call()
    assert len(scripted.calls) == 2  # the open breaker did not reach the provider

    breaker = resilience.get_breaker("anthropic")
    breaker._open_until = 0.0  # reset window elapsed
    scripted.script = [_reply("back")]
    assert _call().content[0]["text"] == "back"
    assert not breaker.is_open


def test_bad_requests_do_not_trip_the_breaker(scripted, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "llm_circuit_breaker_failures", 1)
    scripted.script = [LLMBadRequestError("bad"), _reply()]
    with pytest.raises(LLMBadRequestError):
        _call()
    _call()


def test_fallback_provider_takes_over(scripted, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(ProviderRegistry._providers, "openai_compatible", ScriptedProvider)
    monkeypatch.setattr(settings, "llm_fallback_provider", "ollama")
    monkeypatch.setattr(settings, "llm_fallback_model", "llama3.1")
    scripted.script = [LLMUnavailableError("primary down"), _reply("from fallback")]
    out = gateway.create_message(model="claude-x", max_tokens=10, messages=[], thinking={"type": "enabled"})
    assert out.content[0]["text"] == "from fallback"
    fallback_call = scripted.calls[1]
    assert fallback_call["provider"] == "openai_compatible"
    assert fallback_call["model"] == "llama3.1"  # the primary's model name is replaced
    assert "thinking" not in fallback_call  # dropped: the fallback has no extended thinking


def test_no_fallback_for_non_retryable_errors(scripted, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(ProviderRegistry._providers, "openai_compatible", ScriptedProvider)
    monkeypatch.setattr(settings, "llm_fallback_provider", "ollama")
    monkeypatch.setattr(settings, "llm_fallback_model", "llama3.1")
    scripted.script = [LLMAuthError("bad key"), _reply()]
    with pytest.raises(LLMAuthError):
        _call()


def test_usage_is_charged_exactly_once(scripted) -> None:
    from src.agents import tool_agent

    scripted.script = [_reply(tokens=(600, 500)), _reply(tokens=(60, 50))]
    with run_llm_budget(1200):
        msg = _call()  # 1100 of 1200
        tool_agent._record_message_usage(msg)  # legacy callers still call this: it must not charge again
        with pytest.raises(RunBudgetExceeded):
            _call()  # 1100 + 110 > 1200


def test_is_enabled_is_false_when_unconfigured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "llm_provider", "")
    assert gateway.is_enabled() is False
    report = gateway.health()
    assert report["ok"] is False and "LLM_PROVIDER" in report["detail"]


def test_missing_optional_dependency_is_a_clear_config_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(ProviderRegistry._providers, "bedrock", "src.llm.providers.does_not_exist:Nope")
    config = LLMConfig(provider="bedrock", base_url="", api_key="", models={"default": "m"})
    with pytest.raises(LLMConfigError, match="not installed"):
        ProviderRegistry.create("bedrock", config)


def test_health_reports_provider_and_capabilities(scripted) -> None:
    report = gateway.health()
    assert report["ok"] is True
    assert report["provider"] == "anthropic"
    assert report["capabilities"]["tools"] is True
