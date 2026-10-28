"""OpenAI-compatible (incl. SSE streaming), Azure OpenAI and Bedrock providers against fake transports/clients."""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest

from src.llm.config import LLMConfig
from src.llm.errors import LLMAuthError, LLMBadRequestError, LLMRateLimitError, LLMTimeoutError, LLMUnavailableError
from src.llm.providers.azure_openai import AzureOpenAIProvider
from src.llm.providers.openai_compatible import OpenAICompatibleProvider


def _config(provider: str = "openai_compatible", **overrides: Any) -> LLMConfig:
    options = {"supports_tools": True, "supports_vision": True, "max_tokens_param": "auto", "stream_usage": True,
               "reasoning_model_prefixes": ("o1", "o3", "o4", "gpt-5"), "extra_headers": {}}
    options.update(overrides.pop("options", {}))
    values: dict[str, Any] = {"provider": provider, "base_url": "https://api.example/v1", "api_key": "sk-test",
                              "models": {"default": "gpt-4.1", "planning": "gpt-4.1", "critique": "gpt-4.1"},
                              "options": options, "preset": "openai"}
    values.update(overrides)
    return LLMConfig(**values)


def _capture(handler) -> tuple[httpx.MockTransport, list[httpx.Request]]:
    seen: list[httpx.Request] = []

    def wrapped(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return handler(request)

    return httpx.MockTransport(wrapped), seen


def _sse(*chunks: dict[str, Any]) -> httpx.Response:
    body = "".join(f"data: {json.dumps(c)}\n\n" for c in chunks) + "data: [DONE]\n\n"
    return httpx.Response(200, headers={"content-type": "text/event-stream"}, content=body.encode())


def test_streaming_assembles_text_tool_calls_and_usage() -> None:
    transport, seen = _capture(lambda r: _sse(
        {"model": "gpt-4.1", "choices": [{"delta": {"content": "Look"}}]},
        {"choices": [{"delta": {"content": "ing up"}}]},
        {"choices": [{"delta": {"tool_calls": [{"index": 0, "id": "call_1", "function": {"name": "search", "arguments": '{"q":'}}]}}]},
        {"choices": [{"delta": {"tool_calls": [{"index": 0, "function": {"arguments": ' "close"}'}}]}, "finish_reason": "tool_calls"}]},
        {"choices": [], "usage": {"prompt_tokens": 12, "completion_tokens": 8, "prompt_tokens_details": {"cached_tokens": 4}}},
    ))
    ticks: list[int] = []
    provider = OpenAICompatibleProvider(_config(), transport=transport)
    msg = provider.create_message(
        stream=True, on_event=lambda: ticks.append(1), model="gpt-4.1", max_tokens=100, temperature=0.2,
        system="sys", messages=[{"role": "user", "content": "hi"}],
        tools=[{"name": "search", "input_schema": {"type": "object"}}],
    )
    assert msg.content == [
        {"type": "text", "text": "Looking up"},
        {"type": "tool_use", "id": "call_1", "name": "search", "input": {"q": "close"}},
    ]
    assert msg.stop_reason == "tool_use"
    assert (msg.usage.input_tokens, msg.usage.output_tokens, msg.usage.cache_read_input_tokens) == (12, 8, 4)
    assert len(ticks) >= 5  # abort polling ran while the stream was read
    body = json.loads(seen[0].content)
    assert body["stream"] is True and body["stream_options"] == {"include_usage": True}
    assert body["max_tokens"] == 100 and body["temperature"] == 0.2
    assert seen[0].headers["authorization"] == "Bearer sk-test"


def test_stream_request_answered_with_plain_json_still_works() -> None:
    reply = {"model": "m", "choices": [{"message": {"content": "whole"}, "finish_reason": "stop"}], "usage": {}}
    transport, _ = _capture(lambda r: httpx.Response(200, json=reply))
    msg = OpenAICompatibleProvider(_config(), transport=transport).create_message(stream=True, model="m", messages=[])
    assert msg.content == [{"type": "text", "text": "whole"}]


def test_reasoning_models_get_max_completion_tokens_and_no_temperature() -> None:
    transport, seen = _capture(lambda r: httpx.Response(200, json={"choices": [{"message": {"content": "x"}}]}))
    OpenAICompatibleProvider(_config(), transport=transport).create_message(model="o3-mini", max_tokens=50, temperature=0.2, messages=[])
    body = json.loads(seen[0].content)
    assert body["max_completion_tokens"] == 50 and "max_tokens" not in body and "temperature" not in body


def test_reasoning_field_is_used_when_content_is_empty() -> None:
    reply = {"choices": [{"message": {"content": "", "reasoning": "the answer"}, "finish_reason": "stop"}]}
    transport, _ = _capture(lambda r: httpx.Response(200, json=reply))
    msg = OpenAICompatibleProvider(_config(), transport=transport).create_message(model="m", messages=[])
    assert msg.content == [{"type": "text", "text": "the answer"}]


@pytest.mark.parametrize(
    ("status", "error", "headers"),
    [(401, LLMAuthError, {}), (403, LLMAuthError, {}), (400, LLMBadRequestError, {}), (404, LLMBadRequestError, {}),
     (429, LLMRateLimitError, {"retry-after": "3"}), (500, LLMUnavailableError, {}), (503, LLMUnavailableError, {})],
)
def test_http_errors_are_mapped(status: int, error: type, headers: dict[str, str]) -> None:
    transport, _ = _capture(lambda r: httpx.Response(status, headers=headers, json={"error": {"message": "nope"}}))
    provider = OpenAICompatibleProvider(_config(), transport=transport)
    for stream in (False, True):
        with pytest.raises(error) as excinfo:
            provider.create_message(stream=stream, model="m", messages=[])
        assert str(status) in str(excinfo.value)
        if status == 429:
            assert excinfo.value.retry_after == 3.0


def test_timeouts_and_connection_failures_are_retryable() -> None:
    def timeout(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow", request=request)

    def refused(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    with pytest.raises(LLMTimeoutError):
        OpenAICompatibleProvider(_config(), transport=httpx.MockTransport(timeout)).create_message(model="m", messages=[])
    with pytest.raises(LLMUnavailableError):
        OpenAICompatibleProvider(_config(), transport=httpx.MockTransport(refused)).create_message(model="m", messages=[])


def test_preset_extra_headers_are_sent() -> None:
    transport, seen = _capture(lambda r: httpx.Response(200, json={"choices": [{"message": {"content": "x"}}]}))
    config = _config(options={"extra_headers": {"X-Title": "Advise Workbench"}}, preset="openrouter")
    OpenAICompatibleProvider(config, transport=transport).create_message(model="m", messages=[])
    assert seen[0].headers["x-title"] == "Advise Workbench"


def test_http_client_is_reused_across_calls() -> None:
    transport, _ = _capture(lambda r: httpx.Response(200, json={"choices": [{"message": {"content": "x"}}]}))
    provider = OpenAICompatibleProvider(_config(), transport=transport)
    provider.create_message(model="m", messages=[])
    client = provider.client
    provider.create_message(model="m", messages=[])
    assert provider.client is client
    provider.close()
    assert provider._client is None


def test_azure_deployment_route_and_api_key_header() -> None:
    transport, seen = _capture(lambda r: httpx.Response(200, json={"choices": [{"message": {"content": "x"}}]}))
    config = _config("azure_openai", base_url="https://res.openai.azure.com", preset="",
                     models={"default": "gpt4o-prod"}, options={"api_version": "2024-10-21"})
    AzureOpenAIProvider(config, transport=transport).create_message(model="gpt4o-prod", messages=[])
    request = seen[0]
    assert str(request.url) == "https://res.openai.azure.com/openai/deployments/gpt4o-prod/chat/completions?api-version=2024-10-21"
    assert request.headers["api-key"] == "sk-test" and "authorization" not in request.headers


def test_azure_v1_route_when_no_api_version() -> None:
    transport, seen = _capture(lambda r: httpx.Response(200, json={"choices": [{"message": {"content": "x"}}]}))
    config = _config("azure_openai", base_url="https://res.openai.azure.com", preset="", options={"api_version": ""})
    AzureOpenAIProvider(config, transport=transport).create_message(model="gpt-4.1", messages=[])
    assert str(seen[0].url) == "https://res.openai.azure.com/openai/v1/chat/completions"
    assert json.loads(seen[0].content)["model"] == "gpt-4.1"


def test_bedrock_uses_anthropic_bedrock_client(monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("anthropic")
    import sys
    import types

    import anthropic

    from src.llm.providers.bedrock import BedrockProvider

    monkeypatch.setitem(sys.modules, "boto3", types.ModuleType("boto3"))
    created: dict[str, Any] = {}

    class FakeMessages:
        def create(self, **kwargs: Any) -> Any:
            created["request"] = kwargs
            return types.SimpleNamespace(content=[{"type": "text", "text": "hi"}], usage=None, stop_reason="end_turn")

    class FakeBedrock:
        def __init__(self, **kwargs: Any) -> None:
            created["client"] = kwargs
            self.messages = FakeMessages()
            self.beta = types.SimpleNamespace(messages=FakeMessages())

        def close(self) -> None:
            pass

    monkeypatch.setattr(anthropic, "AnthropicBedrock", FakeBedrock)
    config = LLMConfig(
        provider="bedrock", base_url="", api_key="", models={"default": "us.anthropic.claude-sonnet-4-5-v1:0"},
        options={"aws_region": "us-east-1", "aws_profile": "", "aws_access_key": "AKIA", "aws_secret_key": "s",
                 "aws_session_token": "", "anthropic_tools": False},
    )
    provider = BedrockProvider(config)
    assert provider.is_enabled() and provider.capabilities.thinking and not provider.capabilities.anthropic_tools
    out = provider.create_message(model="us.anthropic.claude-sonnet-4-5-v1:0", max_tokens=10, messages=[], thinking={"type": "enabled"})
    assert out.content[0]["text"] == "hi"
    assert created["client"] == {"aws_region": "us-east-1", "timeout": 180.0, "max_retries": 0, "aws_access_key": "AKIA", "aws_secret_key": "s"}
    assert created["request"]["thinking"] == {"type": "enabled"}


def test_anthropic_sdk_errors_are_mapped() -> None:
    anthropic = pytest.importorskip("anthropic")
    from src.llm.providers.anthropic_api import map_anthropic_error

    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")

    def status(code: int, headers: dict[str, str] | None = None) -> Exception:
        response = httpx.Response(code, request=request, headers=headers or {}, json={"error": {"message": "x"}})
        return anthropic.APIStatusError("x", response=response, body=None)

    assert isinstance(map_anthropic_error(status(401), "anthropic"), LLMAuthError)
    limited = map_anthropic_error(status(429, {"retry-after": "9"}), "anthropic")
    assert isinstance(limited, LLMRateLimitError) and limited.retry_after == 9.0
    assert isinstance(map_anthropic_error(status(529), "anthropic"), LLMUnavailableError)
    assert isinstance(map_anthropic_error(anthropic.APITimeoutError(request=request), "anthropic"), LLMTimeoutError)
    assert isinstance(map_anthropic_error(anthropic.APIConnectionError(request=request), "anthropic"), LLMUnavailableError)
