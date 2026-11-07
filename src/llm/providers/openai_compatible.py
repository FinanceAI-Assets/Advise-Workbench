"""Any service with an OpenAI-style ``/chat/completions`` endpoint: OpenAI, routers (OpenRouter, LiteLLM),
Groq, Mistral, DeepSeek, Together, xAI and local servers (Ollama, LM Studio). See ``src/llm/presets.py``.

Requests arrive in Anthropic Messages form and are translated; the reply is translated back into
Anthropic-style content blocks (``text`` and ``tool_use``), so agent tool loops work unchanged.
Streaming requests use server-sent events so ``on_event`` (abort polling) runs while the model writes.
"""

from __future__ import annotations

import json
import logging
import threading
from collections.abc import Callable, Iterable
from typing import Any

import httpx

from src.llm.base_provider import BaseLLMProvider, HealthStatus
from src.llm.capabilities import Capabilities
from src.llm.config import LLMConfig
from src.llm.errors import LLMError, LLMTimeoutError, LLMUnavailableError, parse_retry_after, status_error
from src.llm.providers._common import blocks, json_or_empty, message, system_text, tool_result_text

logger = logging.getLogger(__name__)

_CONNECT_TIMEOUT_SEC = 10.0


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


def _anthropic_message(text: str, tool_calls: Iterable[dict[str, Any]], finish: str | None, usage: dict[str, Any], model: str) -> Any:
    content: list[dict[str, Any]] = [{"type": "text", "text": text}] if text else []
    for call in tool_calls:
        fn = call.get("function") or {}
        content.append({"type": "tool_use", "id": call.get("id"), "name": fn.get("name"), "input": json_or_empty(fn.get("arguments"))})
    stop = "tool_use" if any(b["type"] == "tool_use" for b in content) else "max_tokens" if finish == "length" else "end_turn"
    details = usage.get("prompt_tokens_details") or {}
    return message(
        content=content,
        stop_reason=stop,
        input_tokens=usage.get("prompt_tokens", 0),
        output_tokens=usage.get("completion_tokens", 0),
        model=model,
        cache_read_tokens=details.get("cached_tokens", 0) if isinstance(details, dict) else 0,
    )


def _message_text(msg: dict[str, Any]) -> str:
    text = msg.get("content")
    if isinstance(text, list):  # some servers return content parts
        text = "".join(str(p.get("text", "")) for p in text if isinstance(p, dict))
    # Reasoning models on Groq/Ollama may leave content empty and put the answer in "reasoning".
    return str(text or msg.get("reasoning") or "")


def from_openai_response(data: dict[str, Any], model: str) -> Any:
    choice = (data.get("choices") or [{}])[0]
    msg = choice.get("message") or {}
    text = _message_text(msg)
    if not text and not msg.get("tool_calls"):
        logger.warning("Empty completion from model %s (finish_reason=%s)", model, choice.get("finish_reason"))
    return _anthropic_message(text, msg.get("tool_calls") or [], choice.get("finish_reason"), data.get("usage") or {}, str(data.get("model") or model))


class _StreamAccumulator:
    """Rebuilds a complete chat completion from SSE chunks (text, reasoning and tool-call deltas)."""

    def __init__(self, model: str) -> None:
        self.model = model
        self.text: list[str] = []
        self.reasoning: list[str] = []
        self.calls: dict[int, dict[str, Any]] = {}
        self.finish: str | None = None
        self.usage: dict[str, Any] = {}

    def add(self, chunk: dict[str, Any]) -> None:
        if chunk.get("error"):
            raise LLMUnavailableError(f"stream error: {json.dumps(chunk['error'])[:300]}")
        self.model = str(chunk.get("model") or self.model)
        if chunk.get("usage"):
            self.usage = chunk["usage"]
        for choice in chunk.get("choices") or []:
            delta = choice.get("delta") or {}
            if delta.get("content"):
                self.text.append(str(delta["content"]))
            if delta.get("reasoning"):
                self.reasoning.append(str(delta["reasoning"]))
            for call in delta.get("tool_calls") or []:
                slot = self.calls.setdefault(int(call.get("index", 0)), {"id": None, "function": {"name": "", "arguments": ""}})
                slot["id"] = call.get("id") or slot["id"]
                fn = call.get("function") or {}
                slot["function"]["name"] += fn.get("name") or ""
                slot["function"]["arguments"] += fn.get("arguments") or ""
            self.finish = choice.get("finish_reason") or self.finish

    def result(self) -> Any:
        text = "".join(self.text) or "".join(self.reasoning)
        calls = [self.calls[i] for i in sorted(self.calls)]
        return _anthropic_message(text, calls, self.finish, self.usage, self.model)


class OpenAICompatibleProvider(BaseLLMProvider):
    name = "openai_compatible"

    def __init__(self, config: LLMConfig, *, transport: httpx.BaseTransport | None = None) -> None:
        super().__init__(config)
        self._transport = transport
        self._client: httpx.Client | None = None
        self._client_lock = threading.Lock()
        opts = config.options
        self.capabilities = Capabilities(
            tools=bool(opts.get("supports_tools", True)),
            vision=bool(opts.get("supports_vision", True)),
            thinking=False,
            anthropic_tools=False,
        )

    # ----- hooks overridden by AzureOpenAIProvider -----

    def _url(self, model: str) -> str:  # noqa: ARG002 — the model goes in the body here
        return self._config.base_url.rstrip("/") + "/chat/completions"

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json", **(self._config.options.get("extra_headers") or {})}
        if self._config.api_key:
            headers["Authorization"] = f"Bearer {self._config.api_key}"
        return headers

    # ---------------------------------------------------

    def is_enabled(self) -> bool:
        return bool(self._config.models.get("default") and self._config.base_url)

    @property
    def client(self) -> httpx.Client:
        if self._client is None:
            with self._client_lock:
                if self._client is None:
                    self._client = httpx.Client(
                        timeout=httpx.Timeout(self._config.timeout_sec, connect=_CONNECT_TIMEOUT_SEC),
                        transport=self._transport,
                        limits=httpx.Limits(max_connections=64, max_keepalive_connections=16),
                    )
        return self._client

    def _is_reasoning_model(self, model: str) -> bool:
        return model.lower().startswith(tuple(self._config.options.get("reasoning_model_prefixes") or ()))

    def _payload(self, model: str, kwargs: dict[str, Any], stream: bool) -> dict[str, Any]:
        reasoning = self._is_reasoning_model(model)
        param = str(self._config.options.get("max_tokens_param") or "auto")
        if param == "auto":
            param = "max_completion_tokens" if reasoning else "max_tokens"
        payload: dict[str, Any] = {
            "model": model,
            "messages": to_openai_messages(kwargs.get("system"), list(kwargs.get("messages") or [])),
            param: int(kwargs.get("max_tokens") or 4096),
        }
        if kwargs.get("temperature") is not None and not reasoning:  # reasoning models only accept the default
            payload["temperature"] = kwargs["temperature"]
        tools = to_openai_tools(kwargs.get("tools")) if self.capabilities.tools else []
        if tools:
            payload["tools"] = tools
        if stream:
            payload["stream"] = True
            if self._config.options.get("stream_usage"):
                payload["stream_options"] = {"include_usage": True}
        return payload

    def _raise_for_status(self, response: httpx.Response) -> None:
        """Raise the mapped LLMError for an error status; the body must already be read."""
        if response.status_code < 400:
            return
        raise status_error(
            response.status_code,
            f"request failed ({response.status_code}): {response.text[:500]}",
            provider=self._config.label,
            retry_after=parse_retry_after(response.headers.get("retry-after")),
        )

    def create_message(
        self,
        *,
        stream: bool = False,
        beta: bool = False,
        on_event: Callable[[], None] | None = None,
        **kwargs: Any,
    ) -> Any:
        if beta:
            raise LLMError("Anthropic bash / text-editor tools need LLM_PROVIDER=anthropic or bedrock", provider=self._config.label)
        model = str(kwargs.get("model") or self._config.models.get("default") or "")
        if not model:
            raise LLMError("No model configured; set LLM_MODEL in .env", provider=self._config.label)
        payload = self._payload(model, kwargs, stream)
        timeout = kwargs.get("timeout")
        request_timeout = httpx.Timeout(float(timeout), connect=_CONNECT_TIMEOUT_SEC) if timeout else None
        url = self._url(model)
        extra = {"timeout": request_timeout} if request_timeout else {}
        if on_event:
            on_event()
        try:
            if not stream:
                response = self.client.post(url, headers=self._headers(), json=payload, **extra)
                self._raise_for_status(response)
                result = from_openai_response(response.json(), model)
            else:
                acc = _StreamAccumulator(model)
                with self.client.stream("POST", url, headers=self._headers(), json=payload, **extra) as response:
                    if response.status_code >= 400:
                        response.read()
                        self._raise_for_status(response)
                    if "text/event-stream" not in response.headers.get("content-type", ""):
                        response.read()  # the server ignored "stream" and sent one JSON body
                        return self._finish(from_openai_response(response.json(), model), on_event)
                    for line in response.iter_lines():
                        if on_event:
                            on_event()
                        if not line.startswith("data:"):
                            continue
                        data = line[5:].strip()
                        if data == "[DONE]":
                            break
                        if data:
                            acc.add(json.loads(data))
                result = acc.result()
        except httpx.TimeoutException as exc:
            raise LLMTimeoutError(f"no response from {url} in time", provider=self._config.label) from exc
        except httpx.TransportError as exc:
            raise LLMUnavailableError(f"cannot reach {url}: {exc}", provider=self._config.label) from exc
        except ValueError as exc:  # invalid JSON in the body or a chunk
            raise LLMUnavailableError(f"invalid response from {url}: {exc}", provider=self._config.label) from exc
        return self._finish(result, on_event)

    @staticmethod
    def _finish(result: Any, on_event: Callable[[], None] | None) -> Any:
        if on_event:
            on_event()
        return result

    def health_check(self) -> HealthStatus:
        if not self.is_enabled():
            return HealthStatus(ok=False, detail="LLM_MODEL and a base URL are required")
        return HealthStatus(ok=True, detail="configured", info={"base_url": self._config.base_url})

    def close(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None
