"""The locally signed-in Claude Code CLI (``claude -p``). No API key: it uses the CLI's own login.

Each call runs the CLI once with its built-in tools, settings and other MCP servers switched off and a
replacement system prompt, so it behaves like a plain model call. Agent tool loops are delegated: the CLI
runs its own loop and calls this app's tools through the loopback MCP bridge (``tool_bridge.py``), so
``capabilities.delegated_tools`` is True and ``tool_agent`` uses ``run_tool_session``.
Set CLAUDE_CLI_TOOLS_ENABLED=false to fall back to single-call generation.
"""

from __future__ import annotations

import json
import logging
import shutil
import subprocess
import tempfile
from collections.abc import Callable
from contextlib import ExitStack
from pathlib import Path
from typing import Any

from src.llm.base_provider import BaseLLMProvider, HealthStatus, RoundCallback, ToolCallRecord, ToolExecutor
from src.llm.capabilities import Capabilities
from src.llm.config import LLMConfig
from src.llm.errors import LLMBadRequestError, LLMConfigError
from src.llm.providers._common import blocks, message, system_text, tool_result_text
from src.llm.providers.claude_cli.process import classify_failure, clean_env, run_cli
from src.llm.providers.claude_cli.tool_bridge import TOOL_PREFIX, get_bridge
from src.llm.providers.claude_cli.transcript import NO_TOOLS_NOTE, collapse_messages, stdin_payload

__all__ = ["ClaudeCliProvider", "collapse_messages"]

logger = logging.getLogger(__name__)

_HEALTH_TIMEOUT_SEC = 20
# The round limit is enforced from the CLI's printed turns, which normally arrive just before the matching
# tool calls; if a call ever wins that race, this hard cap (max_rounds * value) still bounds the session.
_CALLS_PER_ROUND = 8
_TOOLS_NOTE = (
    "\n\nYour tools are provided by the MCP server '{server}' and are named with the prefix '{prefix}' "
    "(for example {example}). Use them as the instructions above describe."
)


def _workdir() -> str:
    path = Path(tempfile.gettempdir()) / "advise-claude-cli"  # empty folder: no CLAUDE.md is picked up
    path.mkdir(exist_ok=True)
    return str(path)


def _temp_file(stack: ExitStack, text: str, suffix: str) -> str:
    with tempfile.NamedTemporaryFile("w", suffix=suffix, encoding="utf-8", delete=False) as handle:
        handle.write(text)
    stack.callback(lambda: Path(handle.name).unlink(missing_ok=True))
    return handle.name


class _RoundTracker:
    """Turns the CLI's stream-json events into tool rounds: one assistant turn that calls tools = one round."""

    def __init__(self, max_rounds: int, on_round: RoundCallback | None, on_limit: Callable[[], None]) -> None:
        self.max_rounds = max_rounds
        self.on_round = on_round
        self.on_limit = on_limit
        self.rounds = 0
        self._pending: dict[str, tuple[str, dict[str, Any]]] = {}
        self._records: list[ToolCallRecord] = []

    def __call__(self, event: dict[str, Any]) -> None:
        kind = event.get("type")
        content = blocks((event.get("message") or {}).get("content"))
        if kind == "assistant":
            calls = [b for b in content if b.get("type") == "tool_use"]
            if not calls:
                return
            self.flush()
            self.rounds += 1
            if self.rounds > self.max_rounds:
                self.on_limit()  # calls beyond the allowed rounds get "limit reached" so the model writes its answer
            for call in calls:
                name = str(call.get("name") or "")
                self._pending[str(call.get("id"))] = (name.removeprefix(TOOL_PREFIX), call.get("input") or {})
        elif kind == "user":
            for block in content:
                if block.get("type") != "tool_result":
                    continue
                tool_id = str(block.get("tool_use_id"))
                name, tool_input = self._pending.pop(tool_id, ("unknown", {}))
                self._records.append(
                    ToolCallRecord(tool_id, name, tool_input, tool_result_text(block), bool(block.get("is_error")))
                )

    def flush(self) -> None:
        if self._records and self.on_round:
            self.on_round(self.rounds, self._records)
        self._records = []


class ClaudeCliProvider(BaseLLMProvider):
    name = "claude_cli"

    def __init__(self, config: LLMConfig) -> None:
        super().__init__(config)
        tools_on = bool(config.options.get("tools_enabled", True))
        self.capabilities = Capabilities(
            tools=tools_on, vision=True, thinking=False, anthropic_tools=False, delegated_tools=tools_on
        )
        self._binary_path: str | None = None

    def _binary(self) -> str | None:
        if self._binary_path is None:
            self._binary_path = shutil.which(str(self._config.options.get("path") or "claude"))
        return self._binary_path

    def _require_binary(self) -> str:
        binary = self._binary()
        if not binary:
            raise LLMConfigError(
                "Claude CLI not found. Install Claude Code (https://claude.com/claude-code), set CLAUDE_CLI_PATH, "
                "or choose another LLM_PROVIDER in .env",
                provider=self.name,
            )
        return binary

    def is_enabled(self) -> bool:
        return self._binary() is not None

    @property
    def _timeout(self) -> float:
        return float(self._config.options.get("timeout_sec") or 600)

    def _command(self, binary: str, model: str, system_file: str) -> list[str]:
        cmd = [
            binary, "-p",
            "--input-format", "stream-json", "--output-format", "stream-json", "--verbose",
            "--system-prompt-file", system_file,
            "--tools", "", "--setting-sources", "", "--strict-mcp-config", "--no-session-persistence",
        ]
        if model:
            cmd += ["--model", model]
        return cmd

    def _to_message(self, run: Any, model: str, **extra: Any) -> Any:
        result = run.result
        if result is None:
            raise classify_failure(run.stderr or f"exit code {run.returncode}", self.name)
        if result.get("is_error"):
            raise classify_failure(str(result.get("result") or result.get("subtype") or run.stderr), self.name)
        usage = result.get("usage") or {}
        msg = message(
            content=[{"type": "text", "text": str(result.get("result") or "")}],
            stop_reason="end_turn",
            input_tokens=usage.get("input_tokens", 0),
            output_tokens=usage.get("output_tokens", 0),
            cache_read_tokens=usage.get("cache_read_input_tokens", 0),
            cache_creation_tokens=usage.get("cache_creation_input_tokens", 0),
            model=model or str(result.get("model") or ""),
        )
        for key, value in extra.items():
            setattr(msg, key, value)
        return msg

    def create_message(
        self,
        *,
        stream: bool = False,  # noqa: ARG002 — the CLI returns the whole reply at once
        beta: bool = False,
        on_event: Callable[[], None] | None = None,
        **kwargs: Any,
    ) -> Any:
        if beta:
            raise LLMBadRequestError("Anthropic bash / text-editor tools need LLM_PROVIDER=anthropic or bedrock", provider=self.name)
        binary = self._require_binary()
        model = str(kwargs.get("model") or "")
        system = system_text(kwargs.get("system")) + (NO_TOOLS_NOTE if kwargs.get("tools") else "")
        with ExitStack() as stack:
            system_file = _temp_file(stack, system or "You are a helpful assistant.", ".txt")
            run = run_cli(
                self._command(binary, model, system_file),
                stdin_text=stdin_payload(list(kwargs.get("messages") or [])),
                cwd=_workdir(),
                timeout=self._timeout,
                provider=self.name,
                on_event=on_event,
            )
        return self._to_message(run, model)

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
        binary = self._require_binary()
        names = [str(t["name"]) for t in tools if isinstance(t, dict) and t.get("name")]
        try:
            bridge = get_bridge() if names else None
        except OSError:
            logger.warning("Claude CLI tool bridge could not start; writing without tools", exc_info=True)
            bridge = None
        if bridge is None:
            msg = self.create_message(model=model, system=system, messages=messages, on_event=on_event)
            msg.tool_rounds = 0
            return msg

        rounds = max(1, max_rounds)
        prompt = system_text(system) + _TOOLS_NOTE.format(server="advise", prefix=TOOL_PREFIX, example=TOOL_PREFIX + names[0])
        with ExitStack() as stack:
            session = stack.enter_context(bridge.open_session(tools, executor, max_calls=rounds * _CALLS_PER_ROUND))
            tracker = _RoundTracker(rounds, on_round, on_limit=lambda: setattr(session, "exhausted", True))
            system_file = _temp_file(stack, prompt, ".txt")
            config_file = _temp_file(stack, json.dumps(bridge.mcp_config(session)), ".json")
            cmd = self._command(binary, model, system_file) + [
                "--mcp-config", config_file,
                "--allowedTools", ",".join(TOOL_PREFIX + n for n in names),
                "--permission-mode", "dontAsk",
            ]
            run = run_cli(
                cmd,
                stdin_text=stdin_payload(messages),
                cwd=_workdir(),
                timeout=self._timeout,
                provider=self.name,
                on_event=on_event,
                on_message=tracker,
            )
            tracker.flush()
        return self._to_message(run, model, tool_rounds=tracker.rounds)

    def health_check(self) -> HealthStatus:
        binary = self._binary()
        if not binary:
            return HealthStatus(ok=False, detail="Claude CLI not found on PATH (set CLAUDE_CLI_PATH)")
        info: dict[str, Any] = {"path": binary, "tools": self.capabilities.delegated_tools}
        try:
            version = subprocess.run(
                [binary, "--version"], capture_output=True, text=True, timeout=_HEALTH_TIMEOUT_SEC, env=clean_env()
            )
            info["version"] = version.stdout.strip()
            status = subprocess.run(
                [binary, "auth", "status"], capture_output=True, text=True, timeout=_HEALTH_TIMEOUT_SEC, env=clean_env()
            )
            auth = json.loads(status.stdout or "{}")
        except (OSError, subprocess.SubprocessError, ValueError) as exc:
            return HealthStatus(ok=False, detail=f"Claude CLI check failed: {exc}", info=info)
        info["auth_method"] = auth.get("authMethod")
        if not auth.get("loggedIn"):
            return HealthStatus(ok=False, detail="Claude CLI is not signed in; run `claude auth login`", info=info)
        return HealthStatus(ok=True, detail="signed in", info=info)

