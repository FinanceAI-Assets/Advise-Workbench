"""Azure OpenAI. Same chat-completions shape as OpenAI; only the address and auth header differ.

With AZURE_OPENAI_API_VERSION set (the default) requests go to the classic deployment route,
``{endpoint}/openai/deployments/{deployment}/chat/completions?api-version=...``, and the model name is the
deployment name. With it empty they go to the v1 route, ``{endpoint}/openai/v1/chat/completions``.
"""

from __future__ import annotations

from urllib.parse import quote

from src.llm.base_provider import HealthStatus
from src.llm.providers.openai_compatible import OpenAICompatibleProvider


class AzureOpenAIProvider(OpenAICompatibleProvider):
    name = "azure_openai"

    def _url(self, model: str) -> str:
        endpoint = self._config.base_url.rstrip("/")
        version = str(self._config.options.get("api_version") or "")
        if version:
            return f"{endpoint}/openai/deployments/{quote(model, safe='')}/chat/completions?api-version={quote(version)}"
        return f"{endpoint}/openai/v1/chat/completions"

    def _headers(self) -> dict[str, str]:
        return {"Content-Type": "application/json", "api-key": self._config.api_key}

    def is_enabled(self) -> bool:
        return bool(self._config.base_url and self._config.api_key and self._config.models.get("default"))

    def health_check(self) -> HealthStatus:
        if not self.is_enabled():
            return HealthStatus(ok=False, detail="AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_API_KEY and AZURE_OPENAI_DEPLOYMENT are required")
        return HealthStatus(ok=True, detail="configured", info={"endpoint": self._config.base_url})
