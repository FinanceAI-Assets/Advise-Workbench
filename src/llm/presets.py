"""Named OpenAI-compatible endpoints. ``LLM_PROVIDER=<preset>`` selects one; no extra SDK is needed for any."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Preset:
    base_url: str
    key_setting: str = ""  # Settings field holding this service's key ("" -> no key needed, e.g. local servers)
    key_optional: bool = False  # a key is read when set but not required (self-hosted proxies)
    model_setting: str = ""  # Settings field holding a default model for this service
    stream_usage: bool = True  # accepts stream_options.include_usage on streamed requests
    reasoning_model_prefixes: tuple[str, ...] = ()  # models that need max_completion_tokens and no temperature
    extra_headers: tuple[tuple[str, str], ...] = ()


_OPENAI_REASONING = ("o1", "o3", "o4", "gpt-5")

PRESETS: dict[str, Preset] = {
    "openai": Preset(
        "https://api.openai.com/v1", "openai_api_key", model_setting="openai_model", reasoning_model_prefixes=_OPENAI_REASONING
    ),
    "groq": Preset("https://api.groq.com/openai/v1", "groq_api_key"),
    "openrouter": Preset(
        "https://openrouter.ai/api/v1",
        "openrouter_api_key",
        reasoning_model_prefixes=tuple(f"openai/{p}" for p in _OPENAI_REASONING),
        extra_headers=(("X-Title", "Advise Workbench"),),
    ),
    "mistral": Preset("https://api.mistral.ai/v1", "mistral_api_key", stream_usage=False),
    "deepseek": Preset("https://api.deepseek.com/v1", "deepseek_api_key"),
    "together": Preset("https://api.together.xyz/v1", "together_api_key"),
    "xai": Preset("https://api.x.ai/v1", "xai_api_key"),
    "ollama": Preset("http://localhost:11434/v1"),
    "lmstudio": Preset("http://localhost:1234/v1", stream_usage=False),
    "litellm": Preset("http://localhost:4000/v1", "litellm_api_key", key_optional=True),
    # Any other /chat/completions server: LLM_BASE_URL is required and only LLM_API_KEY is sent, so a
    # provider-specific key (OPENAI_API_KEY, ...) never leaks to an arbitrary address.
    "openai_compatible": Preset("", stream_usage=False),
}
