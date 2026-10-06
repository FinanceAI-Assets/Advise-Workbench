"""Run orchestration settings: environment (Settings) first, then config/agent_config.yaml."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from src.core.config import settings

_CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "agent_config.yaml"


@lru_cache(maxsize=1)
def _file_config() -> dict[str, Any]:
    try:
        data = yaml.safe_load(_CONFIG_PATH.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    return data if isinstance(data, dict) else {}


def checkpoint_store() -> str:
    """Where run checkpoints are kept: ``sqlite`` (a file under the workspace) or ``postgres`` (the app database)."""
    section = _file_config().get("langgraph")
    from_file = (section or {}).get("checkpoint_store") if isinstance(section, dict) else ""
    value = str(getattr(settings, "run_checkpoint_store", "") or from_file or "sqlite").strip().lower()
    if value not in ("sqlite", "postgres"):
        raise ValueError(f"RUN_CHECKPOINT_STORE must be sqlite or postgres (got {value!r})")
    return value
