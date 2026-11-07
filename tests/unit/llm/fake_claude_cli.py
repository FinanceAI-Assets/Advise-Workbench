"""Stand-in for the ``claude`` CLI used by test_llm_claude_cli.py. Speaks just enough stream-json and MCP.

Behaviour is chosen with FAKE_CLAUDE_MODE: ok (default), auth_error, usage_limit, hang, crash.
FAKE_CLAUDE_ROUNDS sets how many tool rounds to make when an MCP config is given.
FAKE_CLAUDE_ARGV, when set, receives the argv and visible env flags as JSON.
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.request


def emit(event: dict) -> None:
    sys.stdout.write(json.dumps(event) + "\n")
    sys.stdout.flush()


def mcp(server: dict, method: str, params: dict, req_id: int) -> dict:
    body = json.dumps({"jsonrpc": "2.0", "id": req_id, "method": method, "params": params}).encode()
    headers = {"Content-Type": "application/json", **server.get("headers", {})}
    request = urllib.request.Request(server["url"], data=body, headers=headers)  # noqa: S310 — loopback http only
    with urllib.request.urlopen(request, timeout=10) as response:  # noqa: S310 — loopback http only
        return json.loads(response.read())


def arg(name: str) -> str | None:
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else None


def main() -> int:
    if "--version" in sys.argv:
        print("9.9.9 (Fake Claude)")
        return 0
    if sys.argv[1:3] == ["auth", "status"]:
        print(json.dumps({"loggedIn": True, "authMethod": "claude.ai"}))
        return 0

    stdin_turn = json.loads(sys.stdin.readline())
    if os.environ.get("FAKE_CLAUDE_ARGV"):
        with open(os.environ["FAKE_CLAUDE_ARGV"], "w", encoding="utf-8") as fh:
            json.dump({"argv": sys.argv[1:], "has_api_key": "ANTHROPIC_API_KEY" in os.environ, "stdin": stdin_turn}, fh)

    mode = os.environ.get("FAKE_CLAUDE_MODE", "ok")
    if mode == "hang":
        time.sleep(60)
    if mode == "crash":
        sys.stderr.write("boom: something broke\n")
        return 3
    if mode in ("auth_error", "usage_limit"):
        text = "Invalid API key · Please run /login" if mode == "auth_error" else "Claude AI usage limit reached|1760000000"
        emit({"type": "result", "subtype": "success", "is_error": True, "result": text})
        return 1

    with open(arg("--system-prompt-file"), encoding="utf-8") as fh:
        system = fh.read()
    outputs: list[str] = []
    config_path = arg("--mcp-config")
    if config_path:
        with open(config_path, encoding="utf-8") as fh:
            server = json.load(fh)["mcpServers"]["advise"]
        mcp(server, "initialize", {"protocolVersion": "2025-06-18"}, 1)
        tools = mcp(server, "tools/list", {}, 2)["result"]["tools"]
        name = tools[0]["name"]
        for round_no in range(int(os.environ.get("FAKE_CLAUDE_ROUNDS", "1"))):
            tool_id = f"toolu_{round_no}"
            emit({"type": "assistant", "message": {"content": [
                {"type": "tool_use", "id": tool_id, "name": f"mcp__advise__{name}", "input": {"q": f"round {round_no}"}}]}})
            time.sleep(0.2)  # like the real CLI, the tool call follows the printed turn
            result = mcp(server, "tools/call", {"name": name, "arguments": {"q": f"round {round_no}"}}, 10 + round_no)["result"]
            text = result["content"][0]["text"]
            outputs.append(text)
            emit({"type": "user", "message": {"content": [
                {"type": "tool_result", "tool_use_id": tool_id, "content": [{"type": "text", "text": text}], "is_error": result["isError"]}]}})
    answer = {"system_has_prefix_note": "mcp__advise__" in system, "tool_outputs": outputs}
    emit({"type": "assistant", "message": {"content": [{"type": "text", "text": json.dumps(answer)}]}})
    emit({"type": "result", "subtype": "success", "is_error": False, "result": json.dumps(answer),
          "usage": {"input_tokens": 100, "output_tokens": 20, "cache_read_input_tokens": 7, "cache_creation_input_tokens": 3}})
    return 0


if __name__ == "__main__":
    sys.exit(main())
