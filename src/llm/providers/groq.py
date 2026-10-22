"""Groq API provider implementation.

Groq provides fast LLM inference. This provider supports:
- Fast chat completions
- Multiple models (mixtral-8x7b-32768, llama2-70b, etc.)
- Streaming responses
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from src.llm.base_provider import BaseLLMProvider
from src.llm.capabilities import Capabilities

logger = logging.getLogger(__name__)


class GroqProvider(BaseLLMProvider):
    """Groq API provider using official SDK.

    Fast and efficient LLM inference through Groq API.
    Supports streaming and various open-source models.
    """

    name = "groq"
    # NEW: Add capabilities property required by gateway.py
    # Groq supports function calling (tools), but not vision or extended thinking
    capabilities = Capabilities(tools=True, vision=False, thinking=False, anthropic_tools=False)

    def __init__(self, config: Any) -> None:
        """Initialize Groq provider.

        Args:
            config: LLMConfig with api_key, base_url, models, options

        PHASE 2 (ENVIRONMENT-ONLY):
        All configuration comes from environment variables via LLMConfig.
        No hardcoded defaults for models.

        
        Expected config.models: dict with "default", "planning", "critique" keys

        Commented out (Legacy hardcoded defaults):
        # self.default_models = {
        #     "default": "allam-2-7b",
        #     "planning": "allam-2-7b",
        #     "critique": "allam-2-7b",
        # }
        """
        self._config = config
        self.api_key = config.api_key or ""
        self.base_url = (config.base_url or "https://api.groq.com/openai/v1").rstrip("/")

        # Models from environment variables only (via config.models)
        self.default_models = {
            "default": config.models.get("default", ""),
            "planning": config.models.get("planning", ""),
            "critique": config.models.get("critique", ""),
        }

    def is_enabled(self) -> bool:
        """Check if Groq provider is configured with API key."""
        return bool(self.api_key)

    def create_message(self, stream: bool = False, beta: bool = False, on_event: Callable[[], None] | None = None, **kwargs: Any) -> Any:
        """Create a message using Groq API.

        Args:
            stream: Whether to stream the response
            beta: Unused (for compatibility)
            on_event: Optional callback for streaming events
            **kwargs: Message parameters (model, messages, temperature, max_tokens, etc.)

        Returns:
            Message response with content, usage, stop_reason
        """
        try:
            from groq import Groq
        except ImportError:
            raise RuntimeError(
                "Groq SDK not installed. Install with: pip install groq"
            )

        try:
            client = Groq(api_key=self.api_key)

            # Extract parameters
            model = kwargs.get("model", self.default_models["default"])
            messages = kwargs.get("messages", [])
            temperature = kwargs.get("temperature", 0.2)
            max_tokens = kwargs.get("max_tokens", 2048)

            # Build chat completion request
            chat_params = {
                "model": model,
                "messages": self._normalize_messages(messages),
                "temperature": temperature,
                "max_tokens": max_tokens,
            }

            # Add optional parameters if provided
            if "top_p" in kwargs:
                chat_params["top_p"] = kwargs["top_p"]

            # NEW: Support streaming requests using Groq SDK's stream context manager
            if stream:
                logger.debug(f"Creating streaming message with Groq (model={model})")
                with client.chat.completions.stream(**chat_params) as response_stream:
                    if on_event:
                        on_event()
                    # Get the final message after streaming completes
                    response = response_stream.get_final_message()
                    if on_event:
                        on_event()
                    return self._normalize_response(response)
            else:
                # Original non-streaming path
                logger.debug(f"Creating non-streaming message with Groq (model={model})")
                response = client.chat.completions.create(**chat_params)
                return self._normalize_response(response)

        except Exception as exc:
            # NEW: Log the actual error so Sheldon can properly handle failures
            logger.error(
                f"Groq API call failed: {exc.__class__.__name__}: {exc}",
                exc_info=True
            )
            raise

    def _normalize_messages(self, messages: list[dict[str, Any]]) -> list[dict[str, str]]:
        """Convert message format to Groq/OpenAI format.

        Groq uses OpenAI-compatible format:
        [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]
        """
        normalized = []

        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")

            # If content is a list of blocks (Anthropic format), extract text
            if isinstance(content, list):
                text_parts = []
                for block in content:
                    if isinstance(block, dict):
                        if block.get("type") == "text":
                            text_parts.append(block.get("text", ""))
                    else:
                        text_parts.append(str(block))
                content = " ".join(text_parts)
            else:
                content = str(content)

            normalized.append({
                "role": role,
                "content": content,
            })

        return normalized

    def _normalize_response(self, response: Any) -> Any:
        """Normalize Groq response to standard format.

        Returns response with:
        - content: list of content blocks (Anthropic-style)
        - usage: token usage info
        - stop_reason: why generation stopped
        """
        class NormalizedResponse:
            def __init__(self, groq_response: Any) -> None:
                # Extract text content from first choice
                self.content = []
                self.stop_reason = "stop"  # Default stop reason

                # NEW: Add validation and detailed logging for response processing
                if not groq_response.choices or len(groq_response.choices) == 0:
                    logger.warning("Groq response has no choices")
                else:
                    choice = groq_response.choices[0]

                    # Extract message content
                    if hasattr(choice, "message") and choice.message:
                        message_content = getattr(choice.message, "content", None)
                        if message_content:
                            logger.debug(f"Extracted Groq message content: {len(str(message_content))} chars")
                            self.content.append({
                                "type": "text",
                                "text": str(message_content),
                            })
                        else:
                            logger.warning("Groq message has no content")
                    else:
                        logger.warning("Groq choice has no message")

                    # Extract stop reason (original code had undefined 'choice' if no choices)
                    if hasattr(choice, "finish_reason"):
                        self.stop_reason = choice.finish_reason or "stop"

                # Extract usage information
                self.usage = groq_response.usage if hasattr(groq_response, "usage") else None

                if not self.content:
                    logger.warning("Normalized response has empty content - Sheldon may fall back to generic message")

        return NormalizedResponse(response)
