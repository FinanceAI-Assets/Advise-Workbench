"""Any service with an OpenAI-style ``/chat/completions`` endpoint: OpenAI, Groq, Azure-style gateways, local servers.

Requests arrive in Anthropic Messages form and are translated; the reply is translated back into
Anthropic-style content blocks (``text`` and ``tool_use``), so agent tool loops work unchanged.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

import httpx

from src.llm.capabilities import Capabilities
from src.llm.config import LLMConfig
from src.llm.providers._common import blocks, json_or_empty, message, system_text, tool_result_text

_DEFAULT_BASE_URL = "https://api.openai.com/v1"


def to_openai_messages(system: Any, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    sys_text = system_text(system)
    if sys_text:
        out.append({"role": "system", "content": sys_text})
    for m in messages:
        role = m.get("role", "user")
        parts = blocks(m.get("content"))
        if role == "assistant":
            text = "".join(str(b.get("text", "")) for b in parts if b.get("type") == "text")
            calls = [
                {"id": b.get("id"), "type": "function", "function": {"name": b.get("name"), "arguments": json.dumps(b.get("input") or {})}}
                for b in parts
                if b.get("type") == "tool_use"
            ]
            entry: dict[str, Any] = {"role": "assistant", "content": text or None}
            if calls:
                entry["tool_calls"] = calls
            out.append(entry)
            continue
        # user turn: tool results become their own "tool" messages, the rest stays one user message
        user_parts: list[dict[str, Any]] = []
        for b in parts:
            kind = b.get("type")
            if kind == "tool_result":
                out.append({"role": "tool", "tool_call_id": b.get("tool_use_id"), "content": tool_result_text(b)})
            elif kind == "text":
                user_parts.append({"type": "text", "text": str(b.get("text", ""))})
            elif kind == "image":
                src = b.get("source") or {}
                user_parts.append({"type": "image_url", "image_url": {"url": f"data:{src.get('media_type', 'image/png')};base64,{src.get('data', '')}"}})
        if user_parts:
            only_text = all(p["type"] == "text" for p in user_parts)
            out.append({"role": "user", "content": "\n".join(p["text"] for p in user_parts) if only_text else user_parts})
    return out


def to_openai_tools(tools: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    return [
        {"type": "function", "function": {"name": t.get("name"), "description": t.get("description", ""), "parameters": t.get("input_schema") or {"type": "object", "properties": {}}}}
        for t in tools or []
        if isinstance(t, dict) and t.get("name")
    ]


def from_openai_response(data: dict[str, Any], model: str) -> Any:
    choice = (data.get("choices") or [{}])[0]
    msg = choice.get("message") or {}
    content: list[dict[str, Any]] = []
    text = msg.get("content")
    if isinstance(text, list):  # some servers return content parts
        text = "".join(str(p.get("text", "")) for p in text if isinstance(p, dict))
    if text:
        content.append({"type": "text", "text": str(text)})
    for call in msg.get("tool_calls") or []:
        fn = call.get("function") or {}
        content.append({"type": "tool_use", "id": call.get("id"), "name": fn.get("name"), "input": json_or_empty(fn.get("arguments"))})
    finish = choice.get("finish_reason")
    stop = "tool_use" if any(b["type"] == "tool_use" for b in content) else "max_tokens" if finish == "length" else "end_turn"
    usage = data.get("usage") or {}
    return message(
        content=content,
        stop_reason=stop,
        input_tokens=usage.get("prompt_tokens", 0),
        output_tokens=usage.get("completion_tokens", 0),
        model=str(data.get("model") or model),
    )


class OpenAICompatibleProvider:
    name = "openai_compatible"

    def __init__(self, config: LLMConfig, *, transport: httpx.BaseTransport | None = None) -> None:
        self._config = config
        self._transport = transport
        opts = config.options
        self.capabilities = Capabilities(
            tools=bool(opts.get("supports_tools", True)),
            vision=bool(opts.get("supports_vision", True)),
            thinking=False,
            anthropic_tools=False,
        )

    @property
    def default_models(self) -> dict[str, str]:
        return {"default": "", "planning": "", "critique": ""}  # must be set in model_config.yaml or LLM_MODEL

    def is_enabled(self) -> bool:
        # A local server needs no key, but then the address must be given explicitly.
        return bool(self._config.models.get("default")) and bool(self._config.api_key or self._config.base_url)

    def create_message(
        self,
        *,
        stream: bool = False,  # noqa: ARG002 — one request, whole reply
        beta: bool = False,
        on_event: Callable[[], None] | None = None,
        **kwargs: Any,
    ) -> Any:
        if beta:
            raise RuntimeError("Anthropic bash / text-editor tools need LLM_PROVIDER=anthropic")
        model = str(kwargs.get("model") or self._config.models.get("default") or "")
        if not model:
            raise RuntimeError("No model configured: set LLM_MODEL or models.default in config/model_config.yaml")
        payload: dict[str, Any] = {
            "model": model,
            "messages": to_openai_messages(kwargs.get("system"), list(kwargs.get("messages") or [])),
            str(self._config.options.get("max_tokens_param") or "max_tokens"): int(kwargs.get("max_tokens") or 4096),
        }
        if kwargs.get("temperature") is not None:
            payload["temperature"] = kwargs["temperature"]
        tools = to_openai_tools(kwargs.get("tools")) if self.capabilities.tools else []
        if tools:
            payload["tools"] = tools
        headers = {"Content-Type": "application/json"}
        if self._config.api_key:
            headers["Authorization"] = f"Bearer {self._config.api_key}"
        url = (self._config.base_url or _DEFAULT_BASE_URL).rstrip("/") + "/chat/completions"
        timeout = float(kwargs.get("timeout") or 120.0)
        if on_event:
            on_event()
        with httpx.Client(timeout=max(timeout, 120.0), transport=self._transport) as client:
            response = client.post(url, headers=headers, json=payload)
        if on_event:
            on_event()
        if response.status_code >= 400:
            raise RuntimeError(f"{self.name} request failed ({response.status_code}): {response.text[:500]}")
        return from_openai_response(response.json(), model)
