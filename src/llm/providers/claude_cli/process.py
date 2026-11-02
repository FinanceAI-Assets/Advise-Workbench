"""Run ``claude -p`` once and read its stream-json output as it arrives.

Output is read on a background thread so the caller sees each event live (tool rounds are reported
while the CLI works) and ``on_event`` keeps polling for aborts. The process is killed on abort, timeout
or any other exception, and never inherits API credentials: the CLI must use its own sign-in.
"""

from __future__ import annotations

import json
import os
import queue
import re
import subprocess
import sys
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from src.llm.errors import LLMAuthError, LLMError, LLMRateLimitError, LLMTimeoutError, LLMUnavailableError

STRIPPED_ENV = ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_BASE_URL")
_POLL_SEC = 0.5
_EOF = object()

_AUTH_PATTERN = re.compile(r"/login|not logged in|invalid api key|authentication|unauthori[sz]ed|\b401\b", re.I)
_LIMIT_PATTERN = re.compile(r"usage limit|rate limit|too many requests|\b429\b", re.I)
_UNAVAILABLE_PATTERN = re.compile(r"overloaded|\b5\d\d\b|api error|connection|network|ECONNRE", re.I)


@dataclass
class CliRun:
    result: dict[str, Any] | None  # the final {"type": "result", ...} event
    stderr: str
    returncode: int | None


def clean_env() -> dict[str, str]:
    return {k: v for k, v in os.environ.items() if k not in STRIPPED_ENV}


def classify_failure(text: str, provider: str) -> LLMError:
    """Map CLI error text (result message or stderr) to an LLMError."""
    snippet = text.strip()[:500] or "no output"
    if _AUTH_PATTERN.search(snippet):
        return LLMAuthError(f"Claude CLI is not signed in or was rejected; run `claude auth login`. ({snippet})", provider=provider)
    if _LIMIT_PATTERN.search(snippet):
        return LLMRateLimitError(snippet, provider=provider)
    if _UNAVAILABLE_PATTERN.search(snippet):
        return LLMUnavailableError(snippet, provider=provider)
    return LLMError(f"Claude CLI error: {snippet}", provider=provider)


def run_cli(
    cmd: list[str],
    *,
    stdin_text: str,
    cwd: str,
    timeout: float,
    provider: str,
    on_event: Callable[[], None] | None = None,
    on_message: Callable[[dict[str, Any]], None] | None = None,
) -> CliRun:
    """Run the CLI to completion. ``on_message`` receives every stream-json event except the final result."""
    proc = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=cwd,
        env=clean_env(),
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0) if sys.platform == "win32" else 0,
    )
    lines: queue.Queue[Any] = queue.Queue()
    stderr_parts: list[str] = []

    def pump_stdout() -> None:
        assert proc.stdout is not None
        for line in proc.stdout:
            lines.put(line)
        lines.put(_EOF)

    def pump_stderr() -> None:
        assert proc.stderr is not None
        stderr_parts.append(proc.stderr.read())

    readers = [threading.Thread(target=pump_stdout, daemon=True), threading.Thread(target=pump_stderr, daemon=True)]
    for reader in readers:
        reader.start()

    result: dict[str, Any] | None = None
    deadline = time.monotonic() + timeout
    try:
        assert proc.stdin is not None
        try:
            proc.stdin.write(stdin_text)
            proc.stdin.close()
        except (BrokenPipeError, OSError):
            pass  # the process already exited; its stderr explains why
        while True:
            try:
                line = lines.get(timeout=_POLL_SEC)
            except queue.Empty:
                line = None
            if on_event:
                on_event()  # may raise RunAborted
            if time.monotonic() > deadline:
                raise LLMTimeoutError(f"Claude CLI did not finish within {timeout:.0f}s", provider=provider)
            if line is None:
                continue
            if line is _EOF:
                break
            try:
                event = json.loads(line)
            except ValueError:
                continue
            if not isinstance(event, dict):
                continue
            if event.get("type") == "result":
                result = event
            elif on_message:
                on_message(event)
        proc.wait(timeout=30)
    except BaseException:
        proc.kill()
        proc.wait()
        raise
    finally:
        for reader in readers:
            reader.join(timeout=2)
    return CliRun(result=result, stderr="".join(stderr_parts), returncode=proc.returncode)
