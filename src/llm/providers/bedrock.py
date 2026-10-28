"""Claude on AWS Bedrock through ``anthropic.AnthropicBedrock``: same request shape, so tools, vision and thinking carry over.

Credentials come from AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY (/ AWS_SESSION_TOKEN) or AWS_PROFILE in .env,
else boto3's default chain (instance role, SSO cache, ~/.aws). Needs ``anthropic[bedrock]`` (boto3).
"""

from __future__ import annotations

from typing import Any

from src.llm.base_provider import HealthStatus
from src.llm.capabilities import Capabilities
from src.llm.config import LLMConfig
from src.llm.errors import LLMConfigError
from src.llm.providers.anthropic_api import AnthropicProvider


class BedrockProvider(AnthropicProvider):
    name = "bedrock"

    def __init__(self, config: LLMConfig) -> None:
        super().__init__(config)
        self.capabilities = Capabilities(
            tools=True, vision=True, thinking=True, anthropic_tools=bool(config.options.get("anthropic_tools"))
        )

    def is_enabled(self) -> bool:
        return bool(self._config.options.get("aws_region") and self._config.models.get("default"))

    def _new_client(self) -> Any:
        try:
            import boto3  # noqa: F401 — AnthropicBedrock signs requests with botocore
        except ImportError as exc:
            raise LLMConfigError(
                "LLM_PROVIDER=bedrock needs boto3: `pip install -r requirements.txt` (anthropic[bedrock])",
                provider=self.name,
            ) from exc
        import anthropic

        opts = self._config.options
        kwargs: dict[str, Any] = {
            "aws_region": opts.get("aws_region"),
            "timeout": self._config.timeout_sec,
            "max_retries": 0,
        }
        for name in ("aws_access_key", "aws_secret_key", "aws_session_token", "aws_profile"):
            if opts.get(name):
                kwargs[name] = opts[name]
        if self._config.base_url:
            kwargs["base_url"] = self._config.base_url
        return anthropic.AnthropicBedrock(**kwargs)

    def health_check(self) -> HealthStatus:
        if not self.is_enabled():
            return HealthStatus(ok=False, detail="AWS_REGION and BEDROCK_MODEL are required")
        try:
            import boto3  # noqa: F401
        except ImportError:
            return HealthStatus(ok=False, detail="boto3 is not installed (pip install 'anthropic[bedrock]')")
        return HealthStatus(ok=True, detail="configured", info={"region": self._config.options.get("aws_region")})
