"""The locally signed-in Claude Code CLI (``claude -p``). No API key; personal local use.

Each call runs the CLI once with its own tools, settings and MCP servers switched off and a replacement
system prompt, so it behaves like a plain model call. The CLI cannot run this app's tools, so
``capabilities.tools`` is False and callers fall back to single-call generation.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from src.core.config import settings
from src.llm.capabilities import Capabilities
from src.llm.config import LLMConfig
from src.llm.providers._common import blocks, message, system_text, tool_result_text

# Never let the CLI inherit API credentials: it must use its own sign-in.
_STRIPPED_ENV = ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_BASE_URL")
_NO_TOOLS_NOTE = (
    "\n\n(Tool calling is unavailable in this environment. Do not attempt to call tools; "
    "produce your complete final answer directly as text.)"
)


def _block_text(block: dict[str, Any]) -> str:
    kind = block.get("type")
    if kind == "text":
        return str(block.get("text", ""))
    if kind == "tool_use":
        return f"[tool call {block.get('name')}: {json.dumps(block.get('input'))[:2000]}]"
    if kind == "tool_result":
        return f"[tool result]\n{tool_result_text(block)}"
    return ""


def collapse_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Fold a conversation into the content of one user turn (the CLI takes a single turn)."""
    if not messages:
        return [{"type": "text", "text": ""}]
    last = blocks(messages[-1].get("content"))
    keep = [
        {"type": "image", "source": b["source"]} if b.get("type") == "image" else {"type": "text", "text": _block_text(b)}
        for b in last
        if b.get("type") == "image" or _block_text(b)
    ]
    if len(messages) == 1 and messages[-1].get("role") == "user":
        return keep or [{"type": "text", "text": ""}]
    history = []
    for m in messages[:-1]:
        text = "\n".join(t for t in (_block_text(b) for b in blocks(m.get("content"))) if t)
        role = m.get("role", "user")
        history.append(f"<{role}>\n{text}\n</{role}>")
    return [{"type": "text", "text": "Conversation so far:\n" + "\n".join(history) + "\n\nLatest message:\n"}] + keep


class ClaudeCliProvider:
    name = "claude_cli"
    capabilities = Capabilities(tools=False, vision=True, thinking=False, anthropic_tools=False)

    def __init__(self, config: LLMConfig) -> None:
        self._config = config

    @property
    def default_models(self) -> dict[str, str]:
        return {
            "default": settings.anthropic_claude_model,
            "planning": str(getattr(settings, "anthropic_planning_model", "") or ""),
            "critique": str(getattr(settings, "anthropic_critique_model", "") or ""),
        }

    def _binary(self) -> str | None:
        return shutil.which(str(self._config.options.get("path") or "claude"))

    def is_enabled(self) -> bool:
        return self._binary() is not None

    def create_message(
        self,
        *,
        stream: bool = False,  # noqa: ARG002 — the CLI returns the whole reply at once
        beta: bool = False,
        on_event: Callable[[], None] | None = None,
        **kwargs: Any,
    ) -> Any:
        if beta:
            raise RuntimeError("Anthropic bash / text-editor tools need LLM_PROVIDER=anthropic")
        binary = self._binary()
        if not binary:
            raise RuntimeError("Claude CLI not found; install it or set claude_cli.path in config/model_config.yaml")
        model = str(kwargs.get("model") or self.default_models["default"])
        system = system_text(kwargs.get("system")) + (_NO_TOOLS_NOTE if kwargs.get("tools") else "")
        stdin_line = json.dumps({"type": "user", "message": {"role": "user", "content": collapse_messages(list(kwargs.get("messages") or []))}}) + "\n"
        timeout = float(self._config.options.get("timeout_sec") or 600)

        workdir = Path(tempfile.gettempdir()) / "advise-claude-cli"  # empty folder: no CLAUDE.md is picked up
        workdir.mkdir(exist_ok=True)
        with tempfile.NamedTemporaryFile("w", suffix=".txt", encoding="utf-8", delete=False) as sys_file:
            sys_file.write(system or "You are a helpful assistant.")
        cmd = [
            binary, "-p",
            "--input-format", "stream-json", "--output-format", "stream-json", "--verbose",
            "--model", model, "--system-prompt-file", sys_file.name,
            "--tools", "", "--setting-sources", "", "--strict-mcp-config", "--no-session-persistence",
        ]
        env = {k: v for k, v in os.environ.items() if k not in _STRIPPED_ENV}
        proc = subprocess.Popen(
            cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8", cwd=str(workdir), env=env,
        )
        deadline = time.monotonic() + timeout
        pending: str | None = stdin_line
        try:
            while True:
                try:
                    stdout, stderr = proc.communicate(input=pending, timeout=1.0)
                    break
                except subprocess.TimeoutExpired:
                    pending = None  # already written on the first communicate() call
                    if on_event:
                        on_event()  # lets the caller abort a run mid-call
                    if time.monotonic() > deadline:
                        raise TimeoutError(f"Claude CLI timed out after {timeout:.0f}s") from None
        except BaseException:
            proc.kill()
            proc.communicate()
            raise
        finally:
            os.unlink(sys_file.name)

        result: dict[str, Any] | None = None
        for line in stdout.splitlines():
            try:
                event = json.loads(line)
            except ValueError:
                continue
            if isinstance(event, dict) and event.get("type") == "result":
                result = event
        if result is None:
            raise RuntimeError(f"Claude CLI returned no result (exit {proc.returncode}): {stderr.strip()[:500]}")
        if result.get("is_error"):
            raise RuntimeError(f"Claude CLI error: {str(result.get('result') or result.get('subtype'))[:500]}")
        usage = result.get("usage") or {}
        return message(
            content=[{"type": "text", "text": str(result.get("result") or "")}],
            stop_reason="end_turn",
            input_tokens=usage.get("input_tokens", 0),
            output_tokens=usage.get("output_tokens", 0),
            model=model,
        )
