"""Model gateway: provider selection, capability fallbacks and the OpenAI-compatible translation."""

from __future__ import annotations

import json

import httpx
import pytest

from src.core.config import settings
from src.llm import gateway
from src.llm.config import load_llm_config
from src.llm.providers.claude_cli import collapse_messages
from src.llm.providers.openai_compatible import OpenAICompatibleProvider, to_openai_messages, to_openai_tools


@pytest.fixture
def openai_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "llm_provider", "openai_compatible")
    monkeypatch.setattr(settings, "llm_api_key", "test-key")
    monkeypatch.setattr(settings, "llm_base_url", "https://llm.example/v1")
    monkeypatch.setattr(settings, "llm_model", "small-model")
    monkeypatch.setattr(settings, "llm_planning_model", "big-model")


def _use_transport(monkeypatch: pytest.MonkeyPatch, handler) -> list[dict]:
    """Make the gateway build an OpenAI-compatible provider that talks to ``handler``; return the captured requests."""
    seen: list[dict] = []

    def capture(request: httpx.Request) -> httpx.Response:
        seen.append({"url": str(request.url), "auth": request.headers.get("authorization"), "body": json.loads(request.content)})
        return handler(request, len(seen))

    monkeypatch.setattr(gateway, "_build", lambda config: OpenAICompatibleProvider(config, transport=httpx.MockTransport(capture)))
    return seen


def _reply(text: str | None = None, tool_calls: list | None = None, finish: str = "stop") -> httpx.Response:
    message: dict = {"role": "assistant", "content": text}
    if tool_calls:
        message["tool_calls"] = tool_calls
    return httpx.Response(200, json={"model": "small-model", "choices": [{"message": message, "finish_reason": finish}], "usage": {"prompt_tokens": 11, "completion_tokens": 7}})


def test_default_provider_is_anthropic_with_tiered_models(monkeypatch: pytest.MonkeyPatch) -> None:
     
    """
    PHASE 2 (ENVIRONMENT-ONLY):
    Test that all required env vars must be set; no YAML fallback.
    """
    # Commented out (Legacy - expected all env vars empty to default to anthropic):
    # for name in ("llm_provider", "llm_model", "llm_planning_model", "llm_critique_model", "llm_base_url", "llm_api_key"):
    #     monkeypatch.setattr(settings, name, "")
    # monkeypatch.setattr(settings, "anthropic_api_key", "")
    # assert load_llm_config().provider == "anthropic"
    # assert gateway.model_for("default") == settings.anthropic_claude_model
    # assert gateway.model_for("planning") == settings.anthropic_planning_model
    # assert gateway.capabilities().thinking is True
    # assert gateway.is_enabled() is False  # no key
    # monkeypatch.setattr(settings, "anthropic_api_key", "sk-test")
    # assert gateway.is_enabled() is True

    # NEW TEST (PHASE 2): Verify required env vars are validated
    for name in ("llm_provider", "llm_model", "llm_api_key"):
        monkeypatch.setattr(settings, name, "")

    # Missing LLM_PROVIDER should raise ValueError
    with pytest.raises(ValueError, match="LLM_PROVIDER environment variable is required"):
        load_llm_config()

    # Set provider but missing LLM_MODEL
    monkeypatch.setattr(settings, "llm_provider", "anthropic")
    with pytest.raises(ValueError, match="LLM_PROVIDER must be one of"):
        load_llm_config()

    # Set valid provider and model but missing API key
    monkeypatch.setattr(settings, "llm_model", "claude-3-5-sonnet")
    monkeypatch.setattr(settings, "llm_provider", "anthropic")
    with pytest.raises(ValueError, match="LLM_API_KEY environment variable is required"):
        load_llm_config()

    # All required vars set -> should work
    monkeypatch.setattr(settings, "llm_api_key", "sk-ant-v0-test")
    monkeypatch.setattr(settings, "llm_planning_model", "claude-opus-4-1")
    config = load_llm_config()
    assert config.provider == "anthropic"
    assert config.api_key == "sk-ant-v0-test"
    assert config.models["default"] == "claude-3-5-sonnet"
    assert config.models["planning"] == "claude-opus-4-1"



def test_unknown_provider_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "llm_provider", "something_else")
    with pytest.raises(ValueError, match="LLM_PROVIDER"):
        load_llm_config()


def test_openai_models_fall_back_to_default_tier(openai_settings: None) -> None:
    assert gateway.provider_name() == "openai_compatible"
    assert gateway.model_for("default") == "small-model"
    assert gateway.model_for("planning") == "big-model"
    assert gateway.model_for("critique") == "small-model"  # not set -> default
    assert gateway.is_enabled() is True
    assert gateway.capabilities().thinking is False


def test_claude_generate_through_openai_compatible(openai_settings: None, monkeypatch: pytest.MonkeyPatch) -> None:
    from src.llm.claude import claude_generate, claude_generate_json, claude_generate_with_thinking

    seen = _use_transport(monkeypatch, lambda request, n: _reply('{"ok": true}'))
    assert claude_generate(system="Be terse.", user="hello") == '{"ok": true}'
    assert claude_generate_json(system="JSON only.", user="go") == {"ok": True}
    planned = claude_generate_with_thinking(system="Plan.", user="steps")  # no thinking support: plain call
    assert planned["text"] == '{"ok": true}' and planned["thinking_text"] == ""

    first = seen[0]
    assert first["url"] == "https://llm.example/v1/chat/completions"
    assert first["auth"] == "Bearer test-key"
    assert first["body"]["model"] == "small-model"
    assert first["body"]["messages"][0] == {"role": "system", "content": "Be terse."}
    assert first["body"]["messages"][1] == {"role": "user", "content": "hello"}
    assert "thinking" not in seen[2]["body"]


def test_images_are_sent_as_data_urls(openai_settings: None, monkeypatch: pytest.MonkeyPatch) -> None:
    from src.llm.claude import claude_generate_json_with_images

    seen = _use_transport(monkeypatch, lambda request, n: _reply('{"colour": "red"}'))
    assert claude_generate_json_with_images(system="s", user="what colour?", image_bytes=[b"\x89PNG-bytes"]) == {"colour": "red"}
    parts = seen[0]["body"]["messages"][1]["content"]
    assert parts[0] == {"type": "text", "text": "what colour?"}
    assert parts[1]["type"] == "image_url" and parts[1]["image_url"]["url"].startswith("data:image/png;base64,")


def test_agent_tool_loop_round_trip(openai_settings: None, monkeypatch: pytest.MonkeyPatch) -> None:
    from src.agents import tool_agent as claude_tools
    def handler(request: httpx.Request, n: int) -> httpx.Response:
        if n == 1:
            call = {"id": "call_1", "type": "function", "function": {"name": "retrieve_context", "arguments": '{"query": "close calendar"}'}}
            return _reply(None, tool_calls=[call], finish="tool_calls")
        return _reply("# SOP\nDone.")

    seen = _use_transport(monkeypatch, handler)
    calls: list[tuple[str, dict]] = []
    monkeypatch.setattr(claude_tools, "resolve_tool_call", lambda name, tool_input, context: calls.append((name, tool_input)) or {"snippets": ["T+5 close"]})

    tool = {"name": "retrieve_context", "description": "Search the project documents", "input_schema": {"type": "object", "properties": {"query": {"type": "string"}}}}
    out = claude_tools.run_subagent_tool_loop(system="Write SOPs.", user="Write the SOP.", project_id="p_1", tool_defs=[tool], native_context={"project_id": "p_1"})

    assert calls == [("retrieve_context", {"query": "close calendar"})]
    assert out["text"] == "# SOP\nDone." and out["rounds"] == 2
    assert seen[0]["body"]["tools"][0]["function"]["name"] == "retrieve_context"
    second = seen[1]["body"]["messages"]
    assert second[2]["role"] == "assistant" and second[2]["tool_calls"][0]["id"] == "call_1"
    assert second[3]["role"] == "tool" and second[3]["tool_call_id"] == "call_1" and "T+5 close" in second[3]["content"]


def test_provider_errors_are_raised(openai_settings: None, monkeypatch: pytest.MonkeyPatch) -> None:
    _use_transport(monkeypatch, lambda request, n: httpx.Response(401, json={"error": {"message": "bad key"}}))
    with pytest.raises(RuntimeError, match="401"):
        gateway.create_message(model="small-model", max_tokens=10, messages=[{"role": "user", "content": "hi"}])


def test_provider_without_tools_writes_in_one_call(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    PHASE 2 (ENVIRONMENT-ONLY):
    Test claude_cli provider with required env vars set.
    """
    from src.agents import tool_agent as claude_tools
    from src.llm import claude

    # PHASE 2: Set required env vars for claude_cli
    # (claude_cli doesn't need API_KEY, but still needs PROVIDER and MODEL)
    monkeypatch.setattr(settings, "llm_provider", "claude_cli")
    monkeypatch.setattr(settings, "llm_model", "claude-3-5-sonnet-20241022")
    monkeypatch.setattr(settings, "llm_api_key", "")  # Not needed for claude_cli

    # Commented out (Legacy - used empty settings):
    # monkeypatch.setattr(settings, "llm_provider", "claude_cli")

    assert gateway.capabilities().tools is False
    monkeypatch.setattr(claude_tools, "is_claude_enabled", lambda: True)
    monkeypatch.setattr(claude, "claude_generate", lambda **kwargs: "# written directly")
    out = claude_tools.run_subagent_tool_loop(system="s", user="u", project_id="p", tool_defs=[{"name": "t"}], native_context={})
    assert out == {"text": "# written directly", "tool_trace": [], "model": gateway.model_for("default"), "rounds": 1}


def test_message_translation_helpers() -> None:
    messages = [
        {"role": "user", "content": "start"},
        {"role": "assistant", "content": [{"type": "text", "text": "looking"}, {"type": "tool_use", "id": "t1", "name": "search", "input": {"q": "x"}}]},
        {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "t1", "content": "found"}]},
    ]
    converted = to_openai_messages([{"type": "text", "text": "sys", "cache_control": {"type": "ephemeral"}}], messages)
    assert [m["role"] for m in converted] == ["system", "user", "assistant", "tool"]
    assert converted[2]["tool_calls"][0]["function"] == {"name": "search", "arguments": '{"q": "x"}'}
    assert to_openai_tools([{"name": "search", "description": "d", "input_schema": {"type": "object"}}])[0]["function"]["parameters"] == {"type": "object"}

    collapsed = collapse_messages(messages)  # the CLI takes one turn
    assert collapsed[0]["text"].startswith("Conversation so far:") and "[tool call search" in collapsed[0]["text"]
    assert collapsed[1]["text"] == "[tool result]\nfound"
