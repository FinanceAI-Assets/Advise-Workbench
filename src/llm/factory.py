"""Provider factory: name -> implementation, plus a cache of live instances.

Implementations are registered as ``"module:Class"`` strings and imported on first use, so an optional
dependency (boto3 for Bedrock) is only needed when that provider is selected. Instances are cached by
config fingerprint: SDK clients and HTTP connection pools are reused across calls, and a settings change
(or a test monkeypatching settings) produces a fresh instance.
"""

from __future__ import annotations

import importlib
import logging
import threading
from collections import OrderedDict

from src.llm.base_provider import BaseLLMProvider
from src.llm.config import LLMConfig
from src.llm.errors import LLMConfigError

logger = logging.getLogger(__name__)

_CACHE_SIZE = 8


class ProviderRegistry:
    _providers: dict[str, str | type[BaseLLMProvider]] = {
        "anthropic": "src.llm.providers.anthropic_api:AnthropicProvider",
        "bedrock": "src.llm.providers.bedrock:BedrockProvider",
        "claude_cli": "src.llm.providers.claude_cli:ClaudeCliProvider",
        "openai_compatible": "src.llm.providers.openai_compatible:OpenAICompatibleProvider",
        "azure_openai": "src.llm.providers.azure_openai:AzureOpenAIProvider",
    }
    _instances: OrderedDict[str, BaseLLMProvider] = OrderedDict()
    _lock = threading.Lock()

    @classmethod
    def register(cls, name: str, provider: str | type[BaseLLMProvider]) -> None:
        """Add or replace a provider: a ``BaseLLMProvider`` subclass or a ``"module:Class"`` path."""
        if not isinstance(provider, str) and not issubclass(provider, BaseLLMProvider):
            raise TypeError(f"{provider!r} must subclass BaseLLMProvider")
        with cls._lock:
            cls._providers[name] = provider

    @classmethod
    def list_providers(cls) -> list[str]:
        return list(cls._providers)

    @classmethod
    def is_registered(cls, name: str) -> bool:
        return name in cls._providers

    @classmethod
    def provider_class(cls, name: str) -> type[BaseLLMProvider]:
        target = cls._providers.get(name)
        if target is None:
            raise LLMConfigError(f"Unknown provider {name!r}. Available: {', '.join(cls._providers)}")
        if not isinstance(target, str):
            return target
        module_name, _, class_name = target.partition(":")
        try:
            module = importlib.import_module(module_name)
        except ImportError as exc:
            raise LLMConfigError(
                f"Provider {name!r} needs a package that is not installed ({exc.name or exc}). "
                "Run `pip install -r requirements.txt`."
            ) from exc
        provider_cls = getattr(module, class_name)
        with cls._lock:
            cls._providers[name] = provider_cls
        return provider_cls

    @classmethod
    def create(cls, name: str, config: LLMConfig) -> BaseLLMProvider:
        """A new, uncached instance."""
        return cls.provider_class(name)(config)

    @classmethod
    def get(cls, config: LLMConfig) -> BaseLLMProvider:
        """The cached instance for ``config``, created on first use."""
        key = config.fingerprint
        with cls._lock:
            instance = cls._instances.get(key)
            if instance is not None:
                cls._instances.move_to_end(key)
                return instance
        created = cls.create(config.provider, config)
        with cls._lock:
            instance = cls._instances.setdefault(key, created)
            cls._instances.move_to_end(key)
            # Evicted instances are dropped, not closed: another thread may still be mid-call on one.
            while len(cls._instances) > _CACHE_SIZE:
                cls._instances.popitem(last=False)
        if instance is not created:
            _close_quietly(created)  # another thread won the race; this one was never used
        return instance

    @classmethod
    def clear(cls) -> None:
        """Close and drop every cached instance (shutdown, tests)."""
        with cls._lock:
            instances = list(cls._instances.values())
            cls._instances.clear()
        for instance in instances:
            _close_quietly(instance)


def _close_quietly(provider: BaseLLMProvider) -> None:
    try:
        provider.close()
    except Exception:  # noqa: BLE001 — closing must never break a caller
        logger.debug("closing provider %s failed", provider.name, exc_info=True)
