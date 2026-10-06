"""Local bridge: answers Anthropic Messages API requests using the logged-in Claude Code CLI.

Point an app at it with ANTHROPIC_BASE_URL=http://127.0.0.1:8787 (any non-empty ANTHROPIC_API_KEY;
it is ignored). Each request runs `claude -p` once, with Claude Code's own tools, settings and MCP
servers disabled, so it behaves like a plain model call. Custom tools in a request are not executed:
the model is told to answer directly instead. For personal local use only.

Run:  python3.11 scripts/claude_cli_bridge.py   (options: --port 8787 --claude /path/to/claude --timeout 600)
Normally started for you by scripts/run_agent.sh.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

NO_TOOLS_NOTE = (
    "\n\n(Tool calling is unavailable in this environment. Do not attempt to call tools; "
    "produce your complete final answer directly as text.)"
)
# Never let the CLI inherit API credentials or this bridge's own address.
STRIPPED_ENV = ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_BASE_URL")

CONFIG = {"claude": "claude", "timeout": 600.0}
WORKDIR = Path(tempfile.gettempdir()) / "claude-cli-bridge"


def _log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def _system_text(system) -> str:
    if isinstance(system, str):
        return system
    if isinstance(system, list):
        return "\n\n".join(b.get("text", "") for b in system if isinstance(b, dict) and b.get("type") == "text")
    return ""


def _blocks(content) -> list:
    if isinstance(content, str):
        return [{"type": "text", "text": content}]
    return [b for b in (content or []) if isinstance(b, dict)]


def _block_as_text(block: dict) -> str:
    kind = block.get("type")
    if kind == "text":
        return block.get("text", "")
    if kind == "tool_use":
        return f"[tool call {block.get('name')}: {json.dumps(block.get('input'))[:2000]}]"
    if kind == "tool_result":
        inner = block.get("content")
        if isinstance(inner, list):
            inner = "\n".join(b.get("text", "") for b in inner if isinstance(b, dict))
        return f"[tool result]\n{inner}"
    return ""


def _cli_content(messages: list) -> list:
    """Collapse the request's messages into the content of a single CLI user turn."""
    if not messages:
        return [{"type": "text", "text": ""}]
    last = messages[-1]
    last_blocks = _blocks(last.get("content"))
    keep = [
        {"type": "image", "source": b["source"]} if b.get("type") == "image" else {"type": "text", "text": _block_as_text(b)}
        for b in last_blocks
        if b.get("type") == "image" or _block_as_text(b)
    ]
    if len(messages) == 1 and last.get("role") == "user":
        return keep or [{"type": "text", "text": ""}]
    history = []
    for m in messages[:-1]:
        text = "\n".join(t for t in (_block_as_text(b) for b in _blocks(m.get("content"))) if t)
        history.append(f"<{m.get('role', 'user')}>\n{text}\n</{m.get('role', 'user')}>")
    preface = "Conversation so far:\n" + "\n".join(history) + "\n\nLatest message:\n"
    return [{"type": "text", "text": preface}] + keep


def run_cli(model: str, system: str, content: list) -> dict:
    """Run one `claude -p` turn and return its final `result` event."""
    with tempfile.NamedTemporaryFile("w", suffix=".txt", encoding="utf-8", delete=False) as f:
        f.write(system or "You are a helpful assistant.")
    cmd = [
        CONFIG["claude"], "-p",
        "--input-format", "stream-json", "--output-format", "stream-json", "--verbose",
        "--model", model, "--system-prompt-file", f.name,
        "--tools", "", "--setting-sources", "", "--strict-mcp-config", "--no-session-persistence",
    ]
    stdin = json.dumps({"type": "user", "message": {"role": "user", "content": content}}) + "\n"
    env = {k: v for k, v in os.environ.items() if k not in STRIPPED_ENV}
    try:
        proc = subprocess.run(
            cmd, input=stdin, capture_output=True, text=True, encoding="utf-8",
            cwd=str(WORKDIR), env=env, timeout=CONFIG["timeout"],
        )
    finally:
        os.unlink(f.name)
    result = None
    for line in proc.stdout.splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if isinstance(event, dict) and event.get("type") == "result":
            result = event
    if result is None:
        raise RuntimeError(f"claude CLI gave no result (exit {proc.returncode}): {proc.stderr.strip()[:500]}")
    if result.get("is_error"):
        raise RuntimeError(f"claude CLI error: {str(result.get('result') or result.get('subtype'))[:500]}")
    return result


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *args) -> None:  # silence default per-request logging
        pass

    def _send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _sse(self, event: str, data: dict) -> None:
        self.wfile.write(f"event: {event}\ndata: {json.dumps(data)}\n\n".encode())
        self.wfile.flush()

    def do_GET(self) -> None:
        self._send_json(200, {"status": "ok", "bridge": "claude-cli"})

    def do_POST(self) -> None:
        if not self.path.split("?")[0].rstrip("/").endswith("/v1/messages"):
            self._send_json(404, {"type": "error", "error": {"type": "not_found_error", "message": self.path}})
            return
        req = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}")
        model = str(req.get("model") or "claude-haiku-4-5")
        system = _system_text(req.get("system")) + (NO_TOOLS_NOTE if req.get("tools") else "")
        content = _cli_content(req.get("messages") or [])
        msg_id = f"msg_bridge_{uuid.uuid4().hex[:20]}"
        started = time.monotonic()

        if req.get("stream"):
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "close")
            self.end_headers()
            self.close_connection = True
            self._sse("message_start", {"type": "message_start", "message": {
                "id": msg_id, "type": "message", "role": "assistant", "model": model, "content": [],
                "stop_reason": None, "stop_sequence": None, "usage": {"input_tokens": 0, "output_tokens": 0}}})
            box: dict = {}
            worker = threading.Thread(target=lambda: box.update(self._safe_run(model, system, content)))
            worker.start()
            while worker.is_alive():  # keep the client's read timeout from firing while the CLI works
                worker.join(10)
                if worker.is_alive():
                    self._sse("ping", {"type": "ping"})
            if "error" in box:
                self._sse("error", {"type": "error", "error": {"type": "api_error", "message": box["error"]}})
                _log(f"stream  {model}  FAILED after {time.monotonic() - started:.1f}s: {box['error']}")
                return
            text, usage = box["text"], box["usage"]
            self._sse("content_block_start", {"type": "content_block_start", "index": 0,
                                              "content_block": {"type": "text", "text": ""}})
            self._sse("content_block_delta", {"type": "content_block_delta", "index": 0,
                                              "delta": {"type": "text_delta", "text": text}})
            self._sse("content_block_stop", {"type": "content_block_stop", "index": 0})
            self._sse("message_delta", {"type": "message_delta",
                                        "delta": {"stop_reason": "end_turn", "stop_sequence": None},
                                        "usage": {"output_tokens": usage.get("output_tokens", 0)}})
            self._sse("message_stop", {"type": "message_stop"})
            _log(f"stream  {model}  {time.monotonic() - started:.1f}s  {len(text)} chars")
            return

        out = self._safe_run(model, system, content)
        if "error" in out:
            _log(f"message {model}  FAILED after {time.monotonic() - started:.1f}s: {out['error']}")
            self._send_json(500, {"type": "error", "error": {"type": "api_error", "message": out["error"]}})
            return
        self._send_json(200, {
            "id": msg_id, "type": "message", "role": "assistant", "model": model,
            "content": [{"type": "text", "text": out["text"]}],
            "stop_reason": "end_turn", "stop_sequence": None,
            "usage": {"input_tokens": out["usage"].get("input_tokens", 0),
                      "output_tokens": out["usage"].get("output_tokens", 0)},
        })
        _log(f"message {model}  {time.monotonic() - started:.1f}s  {len(out['text'])} chars")

    @staticmethod
    def _safe_run(model: str, system: str, content: list) -> dict:
        try:
            result = run_cli(model, system, content)
            return {"text": str(result.get("result") or ""), "usage": result.get("usage") or {}}
        except Exception as exc:  # reported back to the client as an API error
            return {"error": str(exc)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--port", type=int, default=8787)
    parser.add_argument("--claude", default="claude", help="path to the claude CLI")
    parser.add_argument("--timeout", type=float, default=600.0, help="seconds allowed per CLI call")
    args = parser.parse_args()
    claude = shutil.which(args.claude)
    if not claude:
        sys.exit(f"claude CLI not found ({args.claude!r}); pass --claude /path/to/claude")
    CONFIG.update(claude=claude, timeout=args.timeout)
    WORKDIR.mkdir(exist_ok=True)
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    _log(f"Claude CLI bridge on http://127.0.0.1:{args.port}  (using {claude})")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
