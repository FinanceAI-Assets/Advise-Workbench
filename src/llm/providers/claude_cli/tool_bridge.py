"""Loopback MCP server that lets ``claude -p`` call this app's tools.

The CLI cannot import our Python tools, but it speaks MCP. Each process that makes CLI calls (the API
process or a ``run_execution_worker``) starts one small HTTP server on ``127.0.0.1`` with a random port.
Every tool session registers a random bearer token bound to that session's allowed tools and executor, and
the CLI is pointed at it with ``--mcp-config``. Tools then run in-process, inside a copy of the caller's
context, so run budgets, project/run ids and abort state apply exactly as in the API tool loop.

Implements the MCP Streamable HTTP transport's request/response subset (POST with a JSON body, JSON
reply): initialize, ping, tools/list, tools/call and notifications. No streaming, no batching.
(``src.tools.mcp`` has JSON-RPC helpers for the stdio client, but ``src.llm`` sits below ``src.tools`` in
the layer contract, so the two envelopes are built here.)
"""

from __future__ import annotations

import contextvars
import json
import logging
import os
import secrets
import sys
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from src.llm.base_provider import ToolExecutor

logger = logging.getLogger(__name__)

SERVER_NAME = "advise"
TOOL_PREFIX = f"mcp__{SERVER_NAME}__"  # how the CLI names our tools
_PROTOCOL_VERSION = "2025-06-18"
_MAX_BODY_BYTES = 8 * 1024 * 1024
_LOOPBACK_HOSTS = ("127.0.0.1", "localhost")
LIMIT_REACHED_TEXT = "Tool call limit reached for this task. Do not call more tools; write your final answer now."


def format_json_rpc_response(result: Any, request_id: Any) -> str:
    return json.dumps({"jsonrpc": "2.0", "id": request_id, "result": result}, ensure_ascii=False)


def format_json_rpc_error(code: int, message: str, request_id: Any) -> str:
    return json.dumps({"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}, ensure_ascii=False)


@dataclass
class ToolSession:
    token: str
    tools: list[dict[str, Any]]
    executor: ToolExecutor
    context: contextvars.Context
    max_calls: int
    calls: int = 0
    exhausted: bool = False  # set by the provider once the round limit is reached
    _lock: threading.Lock = field(default_factory=threading.Lock)

    @property
    def tool_names(self) -> set[str]:
        return {str(t.get("name")) for t in self.tools}

    def list_tools(self) -> list[dict[str, Any]]:
        return [
            {
                "name": t["name"],
                "description": t.get("description", ""),
                "inputSchema": t.get("input_schema") or {"type": "object", "properties": {}},
            }
            for t in self.tools
            if t.get("name")
        ]

    def call(self, name: str, arguments: dict[str, Any]) -> tuple[str, bool]:
        with self._lock:
            self.calls += 1
            over_limit = self.exhausted or self.calls > self.max_calls
        if over_limit:
            return LIMIT_REACHED_TEXT, True
        if name not in self.tool_names:
            return json.dumps({"error": f"Tool {name!r} not enabled for this agent"}), True
        # A fresh copy per call: one Context cannot be entered by two threads at once.
        return self.context.copy().run(self.executor, name, arguments)


class _Handler(BaseHTTPRequestHandler):
    server: _BridgeServer
    protocol_version = "HTTP/1.1"
    server_version = "AdviseToolBridge/1.0"

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002 — BaseHTTPRequestHandler signature
        logger.debug("tool bridge: " + format, *args)

    def _send(self, status: int, body: str = "", content_type: str = "application/json") -> None:
        data = body.encode("utf-8")
        self.send_response(status)
        if data:
            self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        if data:
            self.wfile.write(data)

    def _session(self) -> ToolSession | None:
        host = (self.headers.get("Host") or "").rsplit(":", 1)[0].strip("[]")
        if host not in _LOOPBACK_HOSTS:  # blocks DNS-rebinding requests from a browser
            return None
        auth = self.headers.get("Authorization") or ""
        token = auth[7:].strip() if auth.lower().startswith("bearer ") else ""
        return self.server.bridge.lookup(token) if token else None

    def do_POST(self) -> None:  # noqa: N802 — http.server naming
        if self.path.split("?", 1)[0] != "/mcp":
            self._send(404)
            return
        session = self._session()
        if session is None:
            self._send(401, json.dumps({"error": "unauthorized"}))
            return
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0 or length > _MAX_BODY_BYTES:
            self._send(413 if length > 0 else 400)
            return
        try:
            request = json.loads(self.rfile.read(length))
        except ValueError:
            self._send(400, format_json_rpc_error(-32700, "Parse error", None))
            return
        if not isinstance(request, dict):
            self._send(400, format_json_rpc_error(-32600, "Batching is not supported", None))
            return
        reply = _handle(session, request)
        if reply is None:
            self._send(202)
        else:
            self._send(200, reply)

    def do_GET(self) -> None:  # noqa: N802 — no server-initiated stream
        self.send_response(405)
        self.send_header("Allow", "POST")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_DELETE(self) -> None:  # noqa: N802 — session end; sessions are closed by the provider
        self._send(200 if self._session() else 401)


def _handle(session: ToolSession, request: dict[str, Any]) -> str | None:
    method = str(request.get("method") or "")
    req_id = request.get("id")
    if req_id is None:
        return None  # notification (e.g. notifications/initialized)
    params = request.get("params") or {}
    try:
        if method == "initialize":
            return format_json_rpc_response(
                {
                    "protocolVersion": params.get("protocolVersion") or _PROTOCOL_VERSION,
                    "capabilities": {"tools": {"listChanged": False}},
                    "serverInfo": {"name": SERVER_NAME, "version": "1.0"},
                },
                req_id,
            )
        if method == "ping":
            return format_json_rpc_response({}, req_id)
        if method == "tools/list":
            return format_json_rpc_response({"tools": session.list_tools()}, req_id)
        if method == "tools/call":
            arguments = params.get("arguments")
            text, is_error = session.call(str(params.get("name") or ""), arguments if isinstance(arguments, dict) else {})
            return format_json_rpc_response({"content": [{"type": "text", "text": text}], "isError": is_error}, req_id)
        return format_json_rpc_error(-32601, f"Method not found: {method}", req_id)
    except Exception as exc:  # noqa: BLE001 — a tool failure must reach the model as an error, not kill the bridge
        logger.exception("tool bridge: %s failed", method)
        if method == "tools/call":
            body = {"content": [{"type": "text", "text": json.dumps({"error": str(exc)[:800]})}], "isError": True}
            return format_json_rpc_response(body, req_id)
        return format_json_rpc_error(-32603, str(exc)[:300], req_id)


class _BridgeServer(ThreadingHTTPServer):
    daemon_threads = True
    bridge: ToolBridge

    def handle_error(self, request: Any, client_address: Any) -> None:
        # The CLI drops its keep-alive connection when it exits; that is normal, not an error.
        if isinstance(sys.exc_info()[1], (ConnectionResetError, ConnectionAbortedError, BrokenPipeError)):
            return
        logger.warning("tool bridge: error serving %s", client_address, exc_info=True)


class ToolBridge:
    def __init__(self) -> None:
        self._sessions: dict[str, ToolSession] = {}
        self._lock = threading.Lock()
        self._server = _BridgeServer(("127.0.0.1", 0), _Handler)
        self._server.bridge = self
        self.pid = os.getpid()
        threading.Thread(target=self._server.serve_forever, name="claude-cli-tool-bridge", daemon=True).start()

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self._server.server_address[1]}/mcp"

    def lookup(self, token: str) -> ToolSession | None:
        with self._lock:
            session = self._sessions.get(token)
        return session if session and secrets.compare_digest(session.token, token) else None

    @contextmanager
    def open_session(self, tools: list[dict[str, Any]], executor: ToolExecutor, *, max_calls: int) -> Iterator[ToolSession]:
        session = ToolSession(
            token=secrets.token_urlsafe(32),
            tools=[t for t in tools if isinstance(t, dict) and t.get("name")],
            executor=executor,
            context=contextvars.copy_context(),
            max_calls=max_calls,
        )
        with self._lock:
            self._sessions[session.token] = session
        try:
            yield session
        finally:
            with self._lock:
                self._sessions.pop(session.token, None)

    def mcp_config(self, session: ToolSession) -> dict[str, Any]:
        return {
            "mcpServers": {
                SERVER_NAME: {"type": "http", "url": self.url, "headers": {"Authorization": f"Bearer {session.token}"}}
            }
        }

    def shutdown(self) -> None:
        self._server.shutdown()
        self._server.server_close()


_bridge: ToolBridge | None = None
_bridge_lock = threading.Lock()


def get_bridge() -> ToolBridge:
    """The process-wide bridge, started on first use (and restarted in a forked child)."""
    global _bridge
    with _bridge_lock:
        if _bridge is None or _bridge.pid != os.getpid():
            _bridge = ToolBridge()
            logger.info("Claude CLI tool bridge listening on %s", _bridge.url)
        return _bridge
