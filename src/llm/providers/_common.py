"""Helpers shared by the non-Anthropic providers."""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any


def system_text(system: Any) -> str:
    if isinstance(system, str):
        return system
    if isinstance(system, list):
        return "\n\n".join(b.get("text", "") for b in system if isinstance(b, dict) and b.get("type") == "text")
    return ""


def blocks(content: Any) -> list[dict[str, Any]]:
    """Message content as a list of plain dict blocks (SDK objects are converted)."""
    if isinstance(content, str):
        return [{"type": "text", "text": content}]
    out: list[dict[str, Any]] = []
    for block in content or []:
        if isinstance(block, dict):
            out.append(block)
        elif hasattr(block, "model_dump"):
            out.append(block.model_dump(mode="json"))
    return out


def tool_result_text(block: dict[str, Any]) -> str:
    inner = block.get("content")
    if isinstance(inner, list):
        return "\n".join(str(b.get("text", "")) for b in inner if isinstance(b, dict))
    return "" if inner is None else str(inner)


def message(*, content: list[dict[str, Any]], stop_reason: str, input_tokens: int, output_tokens: int, model: str) -> SimpleNamespace:
    """A response shaped like an Anthropic SDK message, with dict content blocks."""
    usage = SimpleNamespace(
        input_tokens=int(input_tokens or 0),
        output_tokens=int(output_tokens or 0),
        cache_read_input_tokens=0,
        cache_creation_input_tokens=0,
    )
    return SimpleNamespace(content=content, stop_reason=stop_reason, usage=usage, model=model, role="assistant", type="message")


def json_or_empty(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    try:
        value = json.loads(raw or "{}")
    except (TypeError, ValueError):
        return {}
    return value if isinstance(value, dict) else {}
