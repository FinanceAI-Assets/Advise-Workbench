"""Claude CLI provider and its loopback MCP tool bridge, driven by a fake ``claude`` executable."""

from __future__ import annotations

import contextvars
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from src.core.config import settings
from src.llm import gateway
from src.llm.errors import LLMAuthError, LLMError, LLMRateLimitError, LLMTimeoutError
from src.llm.providers.claude_cli.tool_bridge import LIMIT_REACHED_TEXT, get_bridge

_FAKE = Path(__file__).with_name("fake_claude_cli.py")
_TOOL = {"name": "lookup", "description": "Look something up", "input_schema": {"type": "object", "properties": {"q": {"type": "string"}}}}


@pytest.fixture
def fake_cli(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A ``claude`` command that runs fake_claude_cli.py; returns the file the fake writes its argv to."""
    if sys.platform == "win32":
        launcher = tmp_path / "claude.cmd"
        launcher.write_text(f'@"{sys.executable}" "{_FAKE}" %*\r\n', encoding="utf-8")
    else:
        launcher = tmp_path / "claude"
        launcher.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{_FAKE}" "$@"\n', encoding="utf-8")
        launcher.chmod(0o755)
    argv_file = tmp_path / "argv.json"
    monkeypatch.setenv("FAKE_CLAUDE_ARGV", str(argv_file))
    monkeypatch.setenv("ANTHROPIC_API_KEY", "must-not-reach-the-cli")
    monkeypatch.setattr(settings, "llm_provider", "claude_cli")
    monkeypatch.setattr(settings, "claude_cli_path", str(launcher))
    monkeypatch.setattr(settings, "claude_cli_tools_enabled", True)
    monkeypatch.setattr(settings, "claude_cli_timeout_sec", 60.0)
    monkeypatch.setattr(settings, "llm_model", "claude-haiku-4-5")
    return argv_file


def test_plain_call_strips_credentials_and_reports_usage(fake_cli: Path) -> None:
    msg = gateway.create_message(model="claude-haiku-4-5", max_tokens=10, system="Be terse.", messages=[{"role": "user", "content": "hi"}])
    assert json.loads(msg.content[0]["text"]) == {"system_has_prefix_note": False, "tool_outputs": []}
    assert (msg.usage.input_tokens, msg.usage.output_tokens, msg.usage.cache_read_input_tokens) == (100, 20, 7)
    recorded = json.loads(fake_cli.read_text())
    assert recorded["has_api_key"] is False
    assert recorded["argv"][recorded["argv"].index("--model") + 1] == "claude-haiku-4-5"
    assert "--mcp-config" not in recorded["argv"]


def test_capabilities_and_health(fake_cli: Path) -> None:
    caps = gateway.capabilities()
    assert caps.tools and caps.delegated_tools and not caps.thinking and not caps.anthropic_tools
    report = gateway.health()
    assert report["ok"] is True and report["info"]["version"] == "9.9.9 (Fake Claude)"


def test_tool_session_runs_app_tools_in_caller_context(fake_cli: Path) -> None:
    marker: contextvars.ContextVar[str] = contextvars.ContextVar("marker", default="lost")
    marker.set("caller-context")
    seen: list[tuple[str, dict, str]] = []
    rounds: list[tuple[int, list[str]]] = []

    def executor(name: str, tool_input: dict) -> tuple[str, bool]:
        seen.append((name, tool_input, marker.get()))
        return f"result for {tool_input['q']}", False

    msg = gateway.run_tool_session(
        system="Use tools.", messages=[{"role": "user", "content": "go"}], tools=[_TOOL], executor=executor, max_rounds=3,
        on_round=lambda n, calls: rounds.append((n, [c.output for c in calls])),
    )
    assert seen == [("lookup", {"q": "round 0"}, "caller-context")]
    assert rounds == [(1, ["result for round 0"])]
    assert msg.tool_rounds == 1
    answer = json.loads(msg.content[0]["text"])
    assert answer == {"system_has_prefix_note": True, "tool_outputs": ["result for round 0"]}
    argv = json.loads(fake_cli.read_text())["argv"]
    assert argv[argv.index("--allowedTools") + 1] == "mcp__advise__lookup"
    assert argv[argv.index("--permission-mode") + 1] == "dontAsk"
    assert "--strict-mcp-config" in argv and argv[argv.index("--tools") + 1] == ""


def test_round_limit_tells_the_model_to_stop(fake_cli: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FAKE_CLAUDE_ROUNDS", "3")
    msg = gateway.run_tool_session(
        system="s", messages=[{"role": "user", "content": "go"}], tools=[_TOOL],
        executor=lambda name, tool_input: ("fine", False), max_rounds=2,
    )
    assert json.loads(msg.content[0]["text"])["tool_outputs"] == ["fine", "fine", LIMIT_REACHED_TEXT]


def test_subagent_tool_loop_delegates_and_emits_rounds(fake_cli: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from src.agents import tool_agent

    monkeypatch.setattr(tool_agent, "resolve_tool_call", lambda name, tool_input, context: {"snippets": [f"{context['project_id']}:{tool_input['q']}"]})
    events: list[tuple[str, dict]] = []
    out = tool_agent.run_subagent_tool_loop(
        system="Write.", user="Write the SOP.", project_id="p_1", tool_defs=[_TOOL], native_context={"project_id": "p_1"},
        emit_event=lambda name, payload: events.append((name, payload)), agent_id="sop",
    )
    assert out["rounds"] == 2 and out["model"] == "claude-haiku-4-5"
    assert [t["tool"] for t in out["tool_trace"]] == ["lookup"] and out["tool_trace"][0]["is_error"] is False
    assert "p_1:round 0" in json.loads(out["text"])["tool_outputs"][0]
    assert events[0][0] == "agent_tool_round" and events[0][1]["agent"] == "sop" and events[0][1]["round"] == 1


def test_tools_outside_the_allow_list_are_refused(fake_cli: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from src.agents import tool_agent

    out_text, is_err = tool_agent._execute_tool("delete_everything", {}, {"lookup"}, {})
    assert is_err and "not enabled" in out_text


@pytest.mark.parametrize(("mode", "error"), [("auth_error", LLMAuthError), ("usage_limit", LLMRateLimitError), ("crash", LLMError)])
def test_cli_failures_are_classified(fake_cli: Path, monkeypatch: pytest.MonkeyPatch, mode: str, error: type) -> None:
    monkeypatch.setenv("FAKE_CLAUDE_MODE", mode)
    with pytest.raises(error):
        gateway.create_message(model="m", max_tokens=5, messages=[{"role": "user", "content": "hi"}])


def test_abort_kills_the_cli_quickly(fake_cli: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FAKE_CLAUDE_MODE", "hang")

    class Aborted(Exception):
        pass

    started = time.monotonic()

    def abort_after_a_second() -> None:
        if time.monotonic() - started > 1.0:
            raise Aborted

    with pytest.raises(Aborted):
        gateway.create_message(on_event=abort_after_a_second, model="m", max_tokens=5, messages=[{"role": "user", "content": "hi"}])
    assert time.monotonic() - started < 10


def test_timeout_is_enforced(fake_cli: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FAKE_CLAUDE_MODE", "hang")
    monkeypatch.setattr(settings, "claude_cli_timeout_sec", 1.5)
    with pytest.raises(LLMTimeoutError):
        gateway.create_message(model="m", max_tokens=5, messages=[{"role": "user", "content": "hi"}])


def test_missing_binary_is_a_config_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "llm_provider", "claude_cli")
    monkeypatch.setattr(settings, "claude_cli_path", "definitely-not-installed-claude")
    assert gateway.is_enabled() is False
    assert gateway.health()["ok"] is False
    with pytest.raises(ValueError, match="Claude CLI not found"):
        gateway.create_message(model="m", max_tokens=5, messages=[])


def _post(url: str, payload: dict, headers: dict[str, str]) -> tuple[int, dict | None]:
    request = urllib.request.Request(url, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json", **headers})  # noqa: S310
    try:
        with urllib.request.urlopen(request, timeout=5) as response:  # noqa: S310 — loopback http only
            body = response.read()
            return response.status, json.loads(body) if body else None
    except urllib.error.HTTPError as exc:
        return exc.code, None


def test_bridge_requires_token_and_loopback_host() -> None:
    bridge = get_bridge()
    with bridge.open_session([_TOOL], lambda name, tool_input: ("ok", False), max_calls=5) as session:
        good = {"Authorization": f"Bearer {session.token}"}
        status, body = _post(bridge.url, {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}, good)
        assert status == 200 and body["result"]["tools"][0]["name"] == "lookup"
        assert body["result"]["tools"][0]["inputSchema"] == _TOOL["input_schema"]
        assert _post(bridge.url, {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}, {"Authorization": "Bearer wrong"})[0] == 401
        assert _post(bridge.url, {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}, {**good, "Host": "evil.example"})[0] == 401
        assert _post(bridge.url, {"jsonrpc": "2.0", "method": "notifications/initialized"}, good)[0] == 202
        status, body = _post(bridge.url, {"jsonrpc": "2.0", "id": 2, "method": "nope"}, good)
        assert body["error"]["code"] == -32601
        token = session.token
    # the session is gone once closed
    assert _post(bridge.url, {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}, {"Authorization": f"Bearer {token}"})[0] == 401


def test_bridge_reports_tool_exceptions_as_tool_errors() -> None:
    def broken(name: str, tool_input: dict) -> tuple[str, bool]:
        raise RuntimeError("tool exploded")

    bridge = get_bridge()
    with bridge.open_session([_TOOL], broken, max_calls=5) as session:
        status, body = _post(
            bridge.url,
            {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "lookup", "arguments": {}}},
            {"Authorization": f"Bearer {session.token}"},
        )
    assert status == 200 and body["result"]["isError"] is True and "tool exploded" in body["result"]["content"][0]["text"]
