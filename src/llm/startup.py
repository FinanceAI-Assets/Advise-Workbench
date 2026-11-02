"""Validate the model provider when the app starts, without delaying startup."""

from __future__ import annotations

import logging
import threading

from src.core.config import settings
from src.llm import gateway
from src.llm.config import load_llm_config
from src.llm.errors import LLMConfigError
from src.llm.factory import ProviderRegistry

logger = logging.getLogger(__name__)


def validate_llm_on_startup() -> None:
    """Check the config now (fast) and the provider's readiness in the background (may run the CLI).

    An invalid config is logged with the env var to fix; with LLM_REQUIRED=true it stops startup instead.
    """
    try:
        config = load_llm_config()
    except LLMConfigError as exc:
        if settings.llm_required:
            raise
        logger.error("LLM provider not configured, model features are unavailable: %s", exc)
        return
    logger.info("LLM provider %s, models %s", config.label, config.models)

    def check() -> None:
        report = gateway.health()
        if report.get("ok"):
            logger.info("LLM provider %s ready (%s); capabilities %s", report["provider"], report.get("detail"), report.get("capabilities"))
        else:
            logger.error("LLM provider %s not ready: %s", report.get("provider"), report.get("detail"))

    threading.Thread(target=check, name="llm-startup-check", daemon=True).start()


def shutdown_llm() -> None:
    ProviderRegistry.clear()
