"""Fold an Anthropic-format conversation into the single user turn ``claude -p`` takes."""

from __future__ import annotations

import json
from typing import Any

from src.llm.providers._common import blocks, tool_result_text

NO_TOOLS_NOTE = (
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
    """Content blocks for one user turn: earlier turns as a transcript, then the latest message (images kept)."""
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


def stdin_payload(messages: list[dict[str, Any]]) -> str:
    """The stream-json input line for ``--input-format stream-json``."""
    turn = {"type": "user", "message": {"role": "user", "content": collapse_messages(messages)}}
    return json.dumps(turn) + "\n"
